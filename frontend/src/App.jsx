import React, { useState, useEffect } from 'react'
import { Layout, Typography, message, Row, Col } from 'antd'
import { io } from 'socket.io-client'
import axios from 'axios'
import BacktestForm from './components/BacktestForm'
import TradeViewChart from './components/TradeViewChart'
import TradeHistory from './components/TradeHistory'
import StatusLog from './components/StatusLog'

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
  const [socket, setSocket] = useState(null)

  useEffect(() => {
    const newSocket = io('http://localhost:5000', {
      transports: ['websocket', 'polling']
    })

    newSocket.on('connect', () => {
      console.log('Connected to WebSocket')
    })

    newSocket.on('progress', (data) => {
      console.log('Progress:', data)
      setStatus(data.status)
      setMessage(data.message)

      if (data.status === 'running') {
        setProgress(Math.round((data.current_step / data.total_steps) * 100) || 50)
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
        message.success('回测完成!')
      }

      if (data.status === 'failed') {
        setLoading(false)
        message.error(data.message)
      }
    })

    setSocket(newSocket)

    return () => {
      newSocket.disconnect()
    }
  }, [])

  const handleSubmit = async (values) => {
    setLoading(true)
    setStatus('pending')
    setProgress(0)
    setResult(null)
    setChartData([])
    setTrades([])

    try {
      const response = await axios.post('http://localhost:5000/api/backtest', values)
      setTaskId(response.data.task_id)
      setStatus('fetching_data')
      setMessage('正在连接回测服务...')
    } catch (error) {
      setLoading(false)
      message.error('提交失败: ' + (error.message || '请确保后端服务已启动'))
    }
  }

  return (
    <Layout style={{ minHeight: '100vh', background: '#0a0a1a' }}>
      <Header style={{ background: '#1a1a2e', padding: '0 24px', display: 'flex', alignItems: 'center' }}>
        <Title level={4} style={{ color: '#fff', margin: 0 }}>A股回测系统</Title>
      </Header>
      <Content style={{ padding: 24, background: '#0a0a1a' }}>
        <Row gutter={16} align="stretch" style={{ height: 'calc(100vh - 120px)' }}>
          <Col span={16} style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <div style={{ flex: '0 0 auto' }}>
              <TradeViewChart data={chartData} trades={trades} result={result} />
            </div>
            <div style={{ flex: 1, minHeight: 0 }}>
              <TradeHistory trades={trades} style={{ height: '100%' }} />
            </div>
          </Col>
          <Col span={8} style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <div style={{ flex: '0 0 auto' }}>
              <StatusLog
                status={status}
                progress={progress}
                message={message_text}
                result={result}
              />
            </div>
            <div style={{ flex: 1, minHeight: 0 }}>
              <BacktestForm onSubmit={handleSubmit} loading={loading} style={{ height: '100%' }} />
            </div>
          </Col>
        </Row>
      </Content>
    </Layout>
  )
}

export default App
