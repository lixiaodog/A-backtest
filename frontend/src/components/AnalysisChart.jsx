import React, { useRef, useEffect } from 'react'
import * as echarts from 'echarts'

function AnalysisChart({ analysis }) {
  const equityChartRef = useRef(null)
  const statsChartRef = useRef(null)

  useEffect(() => {
    if (!analysis) return

    if (equityChartRef.current) {
      const equityChart = echarts.init(equityChartRef.current)

      const equityData = analysis.equity_data || []
      const data = equityData.map(d => d.value || 0)

      const option = {
        title: {
          text: '权益曲线',
          textStyle: { color: '#fff', fontSize: 14 }
        },
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
          top: '30px',
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

      equityChart.setOption(option)
    }

    if (statsChartRef.current) {
      const statsChart = echarts.init(statsChartRef.current)
      const stats = analysis.stats || {}

      const option = {
        title: {
          text: '回测统计',
          textStyle: { color: '#fff', fontSize: 14 }
        },
        tooltip: {
          formatter: (params) => `${params.name}: ${params.value}`
        },
        grid: {
          left: '3%',
          right: '4%',
          bottom: '3%',
          top: '30px',
          containLabel: true
        },
        xAxis: {
          type: 'category',
          data: ['总交易', '盈利', '亏损', '胜率'],
          axisLine: { lineStyle: { color: '#444' } },
          axisLabel: { color: '#888' }
        },
        yAxis: {
          type: 'value',
          axisLine: { lineStyle: { color: '#444' } },
          axisLabel: { color: '#888' },
          splitLine: { lineStyle: { color: '#333' } }
        },
        series: [{
          type: 'bar',
          data: [
            stats.total_trades || 0,
            stats.won_trades || 0,
            stats.lost_trades || 0,
            stats.total_trades > 0 ? ((stats.won_trades || 0) / stats.total_trades * 100).toFixed(1) : 0
          ],
          itemStyle: {
            color: (params) => {
              if (params.dataIndex === 0) return '#1890ff'
              if (params.dataIndex === 1) return '#52c41a'
              if (params.dataIndex === 2) return '#ff4d4f'
              return '#faad14'
            }
          },
          barWidth: '50%'
        }]
      }

      statsChart.setOption(option)
    }
  }, [analysis])

  if (!analysis) return null

  console.log('AnalysisChart rendering with:', analysis)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8, height: '100%' }}>
      <div ref={equityChartRef} style={{ flex: 1, minHeight: 150, background: '#1a1a2e' }} />
      <div ref={statsChartRef} style={{ flex: 1, minHeight: 150, background: '#1a1a2e' }} />
    </div>
  )
}

export default AnalysisChart