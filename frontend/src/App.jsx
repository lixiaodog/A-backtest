import React, { useState, useEffect } from 'react'
import { Layout, Typography, message, Row, Col } from 'antd'
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
  const [message_text, setMessage] = useState('')
  const [result, setResult] = useState(null)
  const [chartData, setChartData] = useState([])
  const [trades, setTrades] = useState([])
  const [logs, setLogs] = useState([])
  const [socket, setSocket] = useState(null)
  const [analysis, setAnalysis] = useState(null)
  const [currentStock, setCurrentStock] = useState('')
  const [liveChartData, setLiveChartData] = useState([])
  const [liveSignals, setLiveSignals] = useState([])

  useEffect(() => {
    const newSocket = io('http://localhost:5000', {
      transports: ['websocket', 'polling']
    })

    newSocket.on('connect', () => {
      console.log('Connected to WebSocket')
      setLogs(prev => [...prev, '[WS] Connected to server'])
    })

    newSocket.on('progress', (data) => {
      console.log('Progress:', data)
      setStatus(data.status)
      setMessage(data.message)
      setLogs(prev => [...prev, `[${data.status}] ${data.message}`])

      if (data.status === 'running') {
        setProgress(data.progress || Math.round((data.current_step / data.total_steps) * 100) || 5)
      }

      if (data.status === 'completed') {
        setLoading(false)
        setProgress(100)
        setResult(data.result)
        if (data.result?.chart_data) {
          setChartData(data.result.chart_data)
        }
        if (data.result?.trades) {
          setTrades(data.result.trades)
        }
        if (data.result?.analysis) {
          setAnalysis(data.result.analysis)
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
        setLiveChartData(prev => {
          const newData = [...prev, data.bar]
          if (newData.length > 500) newData.shift()
          return newData
        })
        if (data.bar_index % 20 === 0) {
          setProgress(Math.round((data.bar_index / 100) * 80 + 10))
        }
        setLogs(prev => [...prev, `[实时K线] bar_index=${data.bar_index}, close=${data.bar.close?.toFixed(2)}`])
      }
    })

    newSocket.on('backtest_signal', (data) => {
      if (data.type === 'trade_signal' && data.signal) {
        setLiveSignals(prev => [...prev, data.signal])
        setLogs(prev => [...prev, `[实时信号] ${data.signal.trade_type === 'buy' ? '买入' : '卖出'} bar_index=${data.signal.bar_index}, price=${data.signal.price?.toFixed(2)}`])
      }
    })

    setSocket(newSocket)

    return () => {
      newSocket.disconnect()
    }
  }, [])

  const handleSubmit = async (values) => {
    setLogs([`[START] Submitting backtest for ${values.stock}...`])
    setLoading(true)
    setStatus('pending')
    setProgress(0)
    setMessage('')
    setResult(null)
    setChartData([])
    setTrades([])
    setAnalysis(null)
    setLiveChartData([])
    setLiveSignals([])
    setCurrentStock(values.stock)

    try {
      const response = await axios.post('http://localhost:5000/api/backtest', values)
      setTaskId(response.data.task_id)
      setStatus('fetching_data')
      setMessage('正在连接回测服务...')
      setLogs(prev => [...prev, '[INFO] Connected to backtest service'])
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
          <Col span={17} style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <div style={{ height: 360, background: '#1a1a2e', borderRadius: 4, position: 'relative' }}>
              <TradeViewChart data={chartData} trades={trades} result={result} stock={currentStock} liveData={liveChartData} liveSignals={liveSignals} />
            </div>
            <div style={{ flex: 1, minHeight: 0 }}>
              <TradeHistory trades={trades} analysis={analysis} />
            </div>
          </Col>
          <Col span={7} style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <div style={{ flex: '0 0 280px' }}>
              <BacktestForm onSubmit={handleSubmit} loading={loading} progress={progress} status={status} />
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
