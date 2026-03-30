import React, { useState, useEffect, useRef } from 'react'
import { Layout, Typography, message, Row, Col, Slider } from 'antd'
import { io } from 'socket.io-client'
import axios from 'axios'
import BacktestForm from './components/BacktestForm'
import TradeViewChart from './components/TradeViewChart'
import TradeHistory from './components/TradeHistory'
import LogOutput from './components/LogOutput'

const { Header, Content } = Layout
const { Title } = Typography

function App() {
  const [loading, setLoading] = useState(false)
  const [taskId, setTaskId] = useState(null)
  const [status, setStatus] = useState('pending')
  const [progress, setProgress] = useState(0)
  const [paused, setPaused] = useState(false)
  const [message_text, setMessage] = useState('')
  const [result, setResult] = useState(null)
  const [chartData, setChartData] = useState([])
  const [trades, setTrades] = useState([])
  const [logs, setLogs] = useState([])
  const [socket, setSocket] = useState(null)
  const [socketId, setSocketId] = useState(null)
  const [analysis, setAnalysis] = useState(null)
  const [currentStock, setCurrentStock] = useState('')
  const [liveChartData, setLiveChartData] = useState([])
  const [liveSignals, setLiveSignals] = useState([])
  const [liveTrades, setLiveTrades] = useState([])
  const [liveEquity, setLiveEquity] = useState([])
  const [liveStats, setLiveStats] = useState(null)
  const [totalBars, setTotalBars] = useState(100)
  const [backtestKey, setBacktestKey] = useState(0)
  const totalBarsRef = useRef(100)
  const [speed, setSpeed] = useState(100)

  useEffect(() => {
    const newSocket = io('http://localhost:5000', {
      transports: ['websocket', 'polling']
    })

    newSocket.on('connect', () => {
      console.log('Connected to WebSocket, id:', newSocket.id)
      setSocketId(newSocket.id)
      setLogs(prev => [...prev, '[WS] Connected to server'])
    })

    newSocket.on('progress', (data) => {
      setStatus(data.status)
      setMessage(data.message)
      setLogs(prev => [...prev, `[${data.status}] ${data.message}`])

      if (data.status === 'running') {
        if (data.total_steps) {
          setTotalBars(data.total_steps)
          totalBarsRef.current = data.total_steps
        }
        setProgress(data.progress || Math.round((data.current_step / data.total_steps) * 100) || 5)
      }

      if (data.status === 'data_loaded') {
        if (data.total_bars) {
          setTotalBars(data.total_bars)
          totalBarsRef.current = data.total_bars
        }
      }

      if (data.status === 'completed') {
        setLoading(false)
        setProgress(100)
        setResult(data.result)
        if (data.result?.analysis) {
          setAnalysis(prev => ({ ...prev, ...data.result.analysis, chart_image_url: data.result.analysis?.chart_image_url }))
        }
        setLogs(prev => [...prev, '[OK] Backtest completed'])
        message.success('回测完成!')
      }

      if (data.status === 'failed') {
        setLoading(false)
        setLogs(prev => [...prev, `[ERROR] ${data.message}`])
        message.error(data.message)
      }
    })

    newSocket.on('backtest_chart', (data) => {
      if (data.type === 'chart_data' && data.bar) {
        setLiveChartData(prev => [...prev, data.bar])
        if (data.bar_index % 20 === 0) {
          const pct = Math.round((data.bar_index / totalBarsRef.current) * 100)
          setProgress(Math.min(99, pct))
        }
        setLogs(prev => [...prev, `[实时K线] bar_index=${data.bar_index}, close=${data.bar.close?.toFixed(2)}`])
      }
    })

    newSocket.on('backtest_signal', (data) => {
      if (data.type === 'trade_signal' && data.signal) {
        const signal = data.signal
        const trade = {
          bar_index: signal.bar_index,
          type: signal.trade_type,
          price: signal.price,
          size: signal.size,
          value: signal.value,
          commission: signal.commission,
          date: signal.time,
          profit: 0
        }
        setLiveSignals(prev => [...prev, signal])
        setLiveTrades(prev => [...prev, trade])
        setLogs(prev => [...prev, `[实时信号] ${signal.trade_type === 'buy' ? '买入' : '卖出'} bar_index=${signal.bar_index}, price=${signal.price?.toFixed(2)}, size=${signal.size}, value=${signal.value?.toFixed(2)}`])
      }
    })

    newSocket.on('backtest_stats', (data) => {
      if (data.type === 'stats_update') {
        if (data.equity_data && data.equity_data.length > 0) {
          setLiveEquity(prev => {
            const newPoint = data.equity_data[data.equity_data.length - 1]
            if (prev.length > 0 && prev[prev.length - 1]?.value === newPoint?.value) {
              return prev
            }
            return [...prev, ...data.equity_data]
          })
        }
        if (data.stats) {
          setLiveStats(prev => {
            if (prev && prev.final_cash === data.stats.final_cash) {
              return prev
            }
            return data.stats
          })
        }
      }
    })

    newSocket.on('backtest_paused', (data) => {
      setPaused(true)
      setLogs(prev => [...prev, `[PAUSED] 回测已暂停`])
    })

    newSocket.on('backtest_resumed', (data) => {
      setPaused(false)
      setLogs(prev => [...prev, `[RESUMED] 回测已恢复`])
    })

    newSocket.on('backtest_stopped', (data) => {
      setLoading(false)
      setStatus('stopped')
      setLogs(prev => [...prev, `[STOPPED] 回测已停止`])
      message.info('回测已停止')
    })

    setSocket(newSocket)

    return () => {
      newSocket.disconnect()
    }
  }, [])

  const handlePause = () => {
    if (socket && taskId) {
      socket.emit('pause_backtest', { task_id: taskId, client_id: socketId })
    }
  }

  const handleStop = () => {
    if (socket && taskId) {
      socket.emit('stop_backtest', { task_id: taskId, client_id: socketId })
    }
  }

  const handleResume = () => {
    if (socket && taskId) {
      socket.emit('resume_backtest', { task_id: taskId, client_id: socketId })
    }
  }

  const handleSubmit = async (values) => {
    setLogs([`[START] Submitting backtest for ${values.stock}...`])
    setLoading(true)
    setStatus('pending')
    setProgress(0)
    setPaused(false)
    setTotalBars(100)
    totalBarsRef.current = 100
    setBacktestKey(prev => prev + 1)
    setMessage('')
    setResult(null)
    setChartData([])
    setTrades([])
    setAnalysis(null)
    setLiveChartData([])
    setLiveSignals([])
    setLiveTrades([])
    setLiveEquity([])
    setLiveStats(null)
    setCurrentStock(values.stock)

    try {
      const submitData = {
        ...values,
        client_id: socketId,
        speed: speed
      }
      const response = await axios.post('http://localhost:5000/api/backtest', submitData)
      setTaskId(response.data.task_id)
      setStatus('fetching_data')
      setMessage('正在连接回测服务...')
      setLogs(prev => [...prev, `[INFO] Connected to backtest service, client_id=${socketId}`])
    } catch (error) {
      setLoading(false)
      setLogs(prev => [...prev, `[ERROR] ${error.message}`])
      message.error('提交失败: ' + (error.message || '请确保后端服务已启动'))
    }
  }

  return (
    <Layout style={{ minHeight: '100vh', background: '#0a0a1a' }}>
      <Header style={{ background: '#1a1a2e', padding: '0 24px', display: 'flex', alignItems: 'center' }}>
        <Title level={4} style={{ color: '#fff', margin: 0 }}>A股回测系统</Title>
      </Header>
      <Content style={{ padding: 12, background: '#0a0a1a' }}>
        <Row gutter={12} style={{ height: 'calc(100vh - 100px)' }}>
          <Col span={17} style={{ display: 'flex', flexDirection: 'column', gap: 8, height: '100%' }}>
            <div style={{ height: 360, background: '#1a1a2e', borderRadius: 4, position: 'relative' }}>
              <TradeViewChart
                key={backtestKey}
                data={chartData}
                trades={trades}
                result={result}
                stock={currentStock}
                liveData={liveChartData}
                liveSignals={liveSignals}
                speedControl={
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{ color: '#888', fontSize: 12 }}>速度:</span>
                    <Slider
                      style={{ width: 120 }}
                      min={1}
                      max={100}
                      value={speed}
                      onChange={(value) => {
                        setSpeed(value)
                        if (socket && taskId) {
                          socket.emit('set_speed', { task_id: taskId, speed: value, client_id: socketId })
                        }
                      }}
                    />
                    <span style={{ color: '#888', fontSize: 12, width: 40 }}>{speed === 100 ? '不限速' : `${speed}%`}</span>
                  </div>
                }
              />
            </div>
            <div style={{ flex: 1, minHeight: 0 }}>
              <TradeHistory trades={trades} analysis={analysis} liveEquity={liveEquity} liveStats={liveStats} liveSignals={liveSignals} liveTrades={liveTrades} />
            </div>
          </Col>
          <Col span={7} style={{ display: 'flex', flexDirection: 'column', gap: 8, height: '100%' }}>
            <div style={{ flex: '0 0 280px' }}>
              <BacktestForm onSubmit={handleSubmit} loading={loading} progress={progress} status={status} paused={paused} onPause={handlePause} onResume={handleResume} onStop={handleStop} />
            </div>
            <div style={{ flex: 1, minHeight: 0 }}>
              <LogOutput logs={logs} />
            </div>
          </Col>
        </Row>
      </Content>
    </Layout>
  )
}

export default App
