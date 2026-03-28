import React, { useEffect, useRef } from 'react'
import { createChart } from 'lightweight-charts'
import { Card, Tag } from 'antd'

function TradeViewChart({ data, trades, result }) {
  const containerRef = useRef(null)
  const chartRef = useRef(null)
  const candlestickSeriesRef = useRef(null)
  const volumeSeriesRef = useRef(null)

  useEffect(() => {
    if (!containerRef.current) return

    const chart = createChart(containerRef.current, {
      layout: {
        background: { type: 'solid', color: '#1a1a2e' },
        textColor: '#d1d4dc',
      },
      grid: {
        vertLines: { color: '#2a2a4a' },
        horzLines: { color: '#2a2a4a' },
      },
      width: containerRef.current.clientWidth,
      height: 350,
    })

    const candlestickSeries = chart.addCandlestickSeries({
      upColor: '#26a69a',
      downColor: '#ef5350',
      borderVisible: false,
      wickUpColor: '#26a69a',
      wickDownColor: '#ef5350',
    })

    const volumeSeries = chart.addHistogramSeries({
      color: '#26a69a',
      priceFormat: { type: 'volume' },
      priceScaleId: '',
    })

    volumeSeries.priceScale().applyOptions({
      scaleMargins: { top: 0.8, bottom: 0 },
    })

    chartRef.current = chart
    candlestickSeriesRef.current = candlestickSeries
    volumeSeriesRef.current = volumeSeries

    const handleResize = () => {
      if (containerRef.current && chartRef.current) {
        chartRef.current.applyOptions({
          width: containerRef.current.clientWidth,
        })
      }
    }

    window.addEventListener('resize', handleResize)

    return () => {
      window.removeEventListener('resize', handleResize)
      chart.remove()
    }
  }, [])

  useEffect(() => {
    if (!candlestickSeriesRef.current) return

    if (!data || data.length === 0) {
      candlestickSeriesRef.current.setData([])
      volumeSeriesRef.current.setData([])
      return
    }

    const chartData = data.map(d => ({
      time: d.time,
      open: d.open,
      high: d.high,
      low: d.low,
      close: d.close,
    }))

    const volumeData = data.map(d => ({
      time: d.time,
      value: d.volume,
      color: d.close >= d.open ? 'rgba(38, 166, 154, 0.5)' : 'rgba(239, 83, 80, 0.5)',
    }))

    candlestickSeriesRef.current.setData(chartData)
    volumeSeriesRef.current.setData(volumeData)
    chartRef.current.timeScale().fitContent()

    const markers = []
    trades?.forEach(trade => {
      let markerTime = trade.date
      if (markerTime) {
        markers.push({
          time: markerTime,
          position: trade.type === 'buy' ? 'belowBar' : 'aboveBar',
          color: trade.type === 'buy' ? '#FF00FF' : '#00FF00',
          shape: trade.type === 'buy' ? 'arrowUp' : 'arrowDown',
          text: trade.type === 'buy' ? '买入' : '卖出',
        })
      }
    })

    if (markers.length > 0) {
      candlestickSeriesRef.current.setMarkers(markers)
    }
  }, [data, trades])

  const renderResultTags = () => {
    if (!result) return null
    return (
      <div style={{ display: 'flex', gap: 4 }}>
        <Tag color="blue">成交 {trades?.length || 0} 笔</Tag>
        <Tag color={result.return_rate >= 0 ? 'green' : 'red'}>
          最终 ¥{result.final_cash?.toFixed(0) || '0'}
        </Tag>
        <Tag color={result.return_rate >= 0 ? 'green' : 'red'}>
          {result.return_rate >= 0 ? '+' : ''}{result.return_rate?.toFixed(2) || '0.00'}%
        </Tag>
      </div>
    )
  }

  return (
    <Card size="small" title="K线图表" extra={renderResultTags()} style={{ height: '100%' }}>
      <div ref={containerRef} style={{ width: '100%' }} />
    </Card>
  )
}

export default TradeViewChart
