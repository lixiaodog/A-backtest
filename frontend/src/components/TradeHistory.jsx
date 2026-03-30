import React, { useRef, useEffect, useState } from 'react'
import { Card, Table, Tag, Tabs, Modal } from 'antd'
import * as echarts from 'echarts'

function EquityChart({ equityData, liveEquity, visible }) {
  const chartRef = useRef(null)
  const chartInstanceRef = useRef(null)
  const lastDataLengthRef = useRef(0)

  const prevVisibleRef = useRef(visible)

  useEffect(() => {
    if (!chartRef.current) return

    const dataToUse = liveEquity && liveEquity.length > 0 ? liveEquity : (equityData || [])
    if (dataToUse.length === 0) return

    if (!chartInstanceRef.current) {
      chartInstanceRef.current = echarts.init(chartRef.current)
    }

    const rawData = dataToUse.map(d => d.value || 0)
    const profitData = rawData.map(v => v - (rawData[0] || 1000000))
    const labels = dataToUse.map(d => d.date || '')

    const chart = chartInstanceRef.current
    chart.setOption({
      tooltip: {
        trigger: 'axis',
        formatter: (params) => {
          const idx = params[0]?.dataIndex
          const value = params[0]?.value || 0
          const sign = value >= 0 ? '+' : ''
          const pct = rawData[idx] ? ((value / rawData[0]) * 100).toFixed(2) : 0
          return `${params[0]?.axisValue || ''}<br/>收益: ${sign}${value.toFixed(2)} (${sign}${pct}%)`
        }
      },
      grid: {
        left: '3%',
        right: '4%',
        bottom: '12%',
        top: '10px',
        containLabel: true
      },
      xAxis: { data: labels },
      yAxis: {
        type: 'value',
        scale: true,
        axisLine: { lineStyle: { color: '#444' } },
        axisLabel: {
          color: '#888',
          formatter: (value) => {
            if (Math.abs(value) >= 10000) return (value / 10000).toFixed(0) + '万'
            if (Math.abs(value) >= 1) return value.toFixed(0)
            return value.toFixed(2)
          }
        },
        splitLine: { lineStyle: { color: '#333' } }
      },
      series: [{
        type: 'line',
        data: profitData,
        smooth: true,
        showSymbol: false,
        lineStyle: { color: '#1890ff', width: 2 },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(24, 144, 255, 0.3)' },
            { offset: 1, color: 'rgba(24, 144, 255, 0.05)' }
          ])
        }
      }]
    })

    chartInstanceRef.current._hasData = true
    const timeout = setTimeout(() => chart.resize(), 100)
    prevVisibleRef.current = visible
    return () => {
      clearTimeout(timeout)
    }
  }, [equityData, liveEquity])

  useEffect(() => {
    if (!chartInstanceRef.current || !chartRef.current) return
    const timeout = setTimeout(() => chartInstanceRef.current?.resize(), 100)
    return () => clearTimeout(timeout)
  }, [visible])

  return (
    <div ref={chartRef} style={{ width: '100%', height: 280 }} />
  )
}

function StatsChart({ stats, visible }) {
  const chartRef = useRef(null)

  useEffect(() => {
    if (!chartRef.current || !stats) return

    const chart = echarts.init(chartRef.current)

    const option = {
      tooltip: { trigger: 'axis' },
      grid: { left: '3%', right: '10%', bottom: '15%', top: '10px', containLabel: true },
      xAxis: {
        type: 'category',
        data: ['总收益', '收益率\n(%)', '总交易', '盈利', '亏损'],
        axisLine: { lineStyle: { color: '#444' } },
        axisLabel: { color: '#888', fontSize: 11 }
      },
      yAxis: [
        {
          type: 'value',
          position: 'left',
          axisLine: { lineStyle: { color: '#444' } },
          axisLabel: { color: '#888' },
          splitLine: { lineStyle: { color: '#333' } }
        },
        {
          type: 'value',
          position: 'right',
          axisLine: { lineStyle: { color: '#444' } },
          axisLabel: { color: '#888' },
          splitLine: { show: false }
        }
      ],
      series: [
        {
          type: 'bar',
          yAxisIndex: 0,
          data: [Math.abs(stats.total_return || 0)],
          itemStyle: { color: '#faad14' },
          barWidth: '40%'
        },
        {
          type: 'bar',
          yAxisIndex: 1,
          data: [0, Math.abs(stats.return_rate || 0), stats.total_trades || 0, stats.won_trades || 0, stats.lost_trades || 0],
          itemStyle: { color: (params) => ['#1890ff', '#52c41a', '#ff4d4f'][params.dataIndex - 1] || '#1890ff' },
          barWidth: '40%'
        }
      ]
    }

    chart.setOption(option)

    const timeout = setTimeout(() => chart.resize(), 100)
    return () => {
      clearTimeout(timeout)
      chart.dispose()
    }
  }, [stats, visible])

  return <div ref={chartRef} style={{ width: '100%', height: 200 }} />
}

function StatsTable({ stats, liveStats, visible }) {
  const statsToUse = liveStats || stats
  if (!statsToUse) return <div style={{ padding: 16, color: '#888' }}>暂无统计数据</div>
  return <StatsChart stats={statsToUse} visible={visible} />
}

function TradeHistory({ trades, analysis, liveEquity, liveStats, liveSignals, liveTrades }) {
  const [activeTab, setActiveTab] = React.useState('trades')
  const columns = [
    {
      title: '时间',
      dataIndex: 'date',
      key: 'date',
      width: 120,
      render: (date) => {
        if (typeof date === 'number') {
          const d = new Date(date * 1000)
          return d.toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' })
        }
        return date
      },
    },
    {
      title: '方向',
      dataIndex: 'type',
      key: 'type',
      width: 70,
      render: (type) => (
        <Tag color={type === 'buy' ? 'green' : 'red'}>
          {type === 'buy' ? '买入' : '卖出'}
        </Tag>
      ),
    },
    {
      title: '成交价',
      dataIndex: 'price',
      key: 'price',
      width: 90,
      render: (price) => price?.toFixed(2),
    },
    {
      title: '数量',
      dataIndex: 'size',
      key: 'size',
      width: 70,
    },
    {
      title: '成交额',
      dataIndex: 'value',
      key: 'value',
      width: 100,
      render: (value) => value?.toFixed(2),
    },
    {
      title: '手续费',
      dataIndex: 'commission',
      key: 'commission',
      width: 80,
      render: (comm) => comm?.toFixed(2),
    },
  ]

  const [modalVisible, setModalVisible] = useState(false)
  const [modalImage, setModalImage] = useState('')

  const tradeList = (trades && trades.length > 0) ? trades : (liveTrades || [])
  const hasTrades = tradeList.length > 0

  const tabItems = [
    {
      key: 'trades',
      label: '交易记录',
      children: hasTrades ? (
        <Table
          dataSource={tradeList}
          columns={columns}
          rowKey={(record, index) => index}
          pagination={false}
          size="small"
          scroll={{ y: 300 }}
        />
      ) : (
        <p style={{ textAlign: 'center', color: '#999' }}>暂无交易记录</p>
      )
    },
    {
      key: 'equity',
      label: '收益曲线',
      children: (
        <div style={{ height: 350 }}>
          {(analysis?.equity_data?.length > 0 || liveEquity?.length > 0) ? (
            <EquityChart equityData={analysis?.equity_data} liveEquity={liveEquity} visible={activeTab === 'equity'} />
          ) : (
            <p style={{ textAlign: 'center', color: '#999' }}>暂无收益数据</p>
          )}
        </div>
      )
    },
    {
      key: 'stats',
      label: '数据统计',
      children: (
        <div style={{ height: 350 }}>
          <StatsTable stats={analysis?.stats} liveStats={liveStats} visible={activeTab === 'stats'} />
        </div>
      )
    },
    {
      key: 'backtrader',
      label: 'Backtrader图表',
      children: (
        <div style={{ height: 350, overflow: 'hidden', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          {analysis?.chart_image_url ? (
            <img
              src={`http://localhost:5000${analysis.chart_image_url}`}
              alt="Backtrader回测图表"
              style={{ maxWidth: '100%', maxHeight: '100%', objectFit: 'contain', cursor: 'pointer' }}
              onClick={() => {
                setModalImage(`http://localhost:5000${analysis.chart_image_url}`)
                setModalVisible(true)
              }}
            />
          ) : (
            <p style={{ textAlign: 'center', color: '#999' }}>暂无回测图表</p>
          )}
        </div>
      )
    },
  ]

  return (
    <>
      <Card size="small" style={{ height: '100%', overflow: 'hidden' }}>
        <Tabs
          items={tabItems}
          size="small"
          activeKey={activeTab}
          onChange={setActiveTab}
          style={{ height: '100%' }}
        />
      </Card>
      <Modal
        open={modalVisible}
        onCancel={() => setModalVisible(false)}
        footer={null}
        width="auto"
        centered
      >
        <img
          src={modalImage}
          alt="Backtrader回测图表"
          style={{ maxWidth: '100%', maxHeight: '80vh', display: 'block', margin: '0 auto' }}
        />
      </Modal>
    </>
  )
}

export default TradeHistory