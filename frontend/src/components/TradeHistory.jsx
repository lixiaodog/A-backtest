import React, { useRef, useEffect } from 'react'
import { Card, Table, Tag, Tabs } from 'antd'
import * as echarts from 'echarts'

function EquityChart({ equityData }) {
  const chartRef = useRef(null)

  useEffect(() => {
    if (!chartRef.current || !equityData || equityData.length === 0) return

    const chart = echarts.init(chartRef.current)

    const data = equityData.map(d => d.value || 0)

    const option = {
      tooltip: {
        trigger: 'axis',
        formatter: (params) => {
          const value = params[0]?.value?.toFixed(2) || 0
          return `资金: ${value}`
        }
      },
      grid: {
        left: '3%',
        right: '4%',
        bottom: '3%',
        top: '10px',
        containLabel: true
      },
      xAxis: {
        type: 'category',
        data: equityData.map((_, i) => i),
        axisLine: { lineStyle: { color: '#444' } },
        axisLabel: { color: '#888' }
      },
      yAxis: {
        type: 'value',
        axisLine: { lineStyle: { color: '#444' } },
        axisLabel: {
          color: '#888',
          formatter: (value) => {
            if (value >= 10000) return (value / 10000).toFixed(0) + '万'
            return value.toFixed(0)
          }
        },
        splitLine: { lineStyle: { color: '#333' } }
      },
      series: [{
        type: 'line',
        data: data,
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
    }

    chart.setOption(option)
  }, [equityData])

  return (
    <div ref={chartRef} style={{ width: '100%', height: 200 }} />
  )
}

function StatsChart({ stats }) {
  const chartRef = useRef(null)

  useEffect(() => {
    if (!chartRef.current || !stats) return

    const chart = echarts.init(chartRef.current)

    const option = {
      tooltip: { trigger: 'axis' },
      grid: { left: '3%', right: '10%', bottom: '3%', top: '10px', containLabel: true },
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
  }, [stats])

  return <div ref={chartRef} style={{ width: '100%', height: 200 }} />
}

function StatsTable({ stats }) {
  if (!stats) return <div style={{ padding: 16, color: '#888' }}>暂无统计数据</div>
  return <StatsChart stats={stats} />
}

function TradeHistory({ trades, analysis }) {
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

  const tradeList = trades || []
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
          scroll={{ y: 200 }}
        />
      ) : (
        <p style={{ textAlign: 'center', color: '#999' }}>暂无交易记录</p>
      )
    },
    {
      key: 'equity',
      label: '收益曲线',
      children: analysis?.equity_data?.length > 0 ? (
        <EquityChart equityData={analysis.equity_data} />
      ) : (
        <p style={{ textAlign: 'center', color: '#999' }}>暂无收益数据</p>
      )
    },
    {
      key: 'stats',
      label: '数据统计',
      children: <StatsTable stats={analysis?.stats} />
    },
  ]

  return (
    <Card size="small" style={{ height: '100%' }}>
      <Tabs
        items={tabItems}
        size="small"
      />
    </Card>
  )
}

export default TradeHistory