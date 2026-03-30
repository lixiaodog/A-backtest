import React, { useState, useEffect } from 'react'
import { Form, Input, DatePicker, Select, Button, Card, InputNumber, Progress } from 'antd'
import dayjs from 'dayjs'

const periods = [
  { value: '1min', label: '1分钟' },
  { value: '5min', label: '5分钟' },
  { value: '15min', label: '15分钟' },
  { value: '30min', label: '30分钟' },
  { value: '60min', label: '60分钟' },
  { value: 'daily', label: '日线' },
  { value: 'weekly', label: '周线' },
  { value: 'monthly', label: '月线' },
]

function BacktestForm({ onSubmit, loading, progress = 0, status, paused, onPause, onResume, onStop, strategies = [] }) {
  const [form] = Form.useForm()
  const [selectedStrategy, setSelectedStrategy] = useState('')
  const [strategyParams, setStrategyParams] = useState([])
  const [formReady, setFormReady] = useState(false)

  useEffect(() => {
    if (strategies.length > 0 && !selectedStrategy) {
      setSelectedStrategy(strategies[0].id)
      setStrategyParams(strategies[0].params || [])
      setFormReady(true)
    }
  }, [strategies])

  useEffect(() => {
    const strategy = strategies.find(s => s.id === selectedStrategy)
    if (strategy) {
      setStrategyParams(strategy.params || [])
      const newInitialValues = { period: 'daily', cash: 1000000, stake: 100 }
      strategy.params.forEach(p => {
        newInitialValues[p.name] = p.default
      })
      form.setFieldsValue(newInitialValues)
    }
  }, [selectedStrategy, strategies])

  const isRunning = loading && !paused
  const canStart = !isRunning && !paused && status !== 'stopped'
  const canPause = isRunning
  const canResume = paused
  const canStop = isRunning || paused

  const handleFinish = (values) => {
    const params = {}
    strategyParams.forEach(p => {
      if (values[p.name] !== undefined) {
        params[p.name] = values[p.name]
      }
    })

    onSubmit({
      stock: values.stock,
      start_date: values.startDate ? values.startDate.format('YYYYMMDD') : '20230101',
      end_date: values.endDate ? values.endDate.format('YYYYMMDD') : '20231231',
      strategy: values.strategy,
      period: values.period || 'daily',
      params,
      cash: values.cash || 1000000,
      stake: values.stake || 100,
    })
  }

  const currentStrategy = strategies.find(s => s.id === selectedStrategy)
  const initialValues = { period: 'daily', cash: 1000000, stake: 100 }
  if (currentStrategy) {
    currentStrategy.params.forEach(p => {
      initialValues[p.name] = p.default
    })
  }

  return (
    <Card size="small" title="参数设置" style={{ height: '100%', overflow: 'auto', width: '100%' }}>
      <Form
        form={form}
        layout="inline"
        onFinish={handleFinish}
        initialValues={initialValues}
      >
        <div style={{ display: 'flex', gap: 16, alignItems: 'center', flexWrap: 'wrap', marginBottom: 8 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <span style={{ fontSize: 12, whiteSpace: 'nowrap' }}>股票代码</span>
            <Form.Item name="stock" rules={[{ required: true }]} style={{ marginBottom: 0 }}>
              <Input placeholder="如: 600519" size="small" style={{ width: 90 }} />
            </Form.Item>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <span style={{ fontSize: 12, whiteSpace: 'nowrap' }}>周期</span>
            <Form.Item name="period" style={{ marginBottom: 0 }}>
              <Select size="small" style={{ width: 70 }}>
                {periods.map(p => (
                  <Select.Option key={p.value} value={p.value}>{p.label}</Select.Option>
                ))}
              </Select>
            </Form.Item>
          </div>
        </div>

        <div style={{ display: 'flex', gap: 16, alignItems: 'center', flexWrap: 'wrap', marginBottom: 8 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <span style={{ fontSize: 12, whiteSpace: 'nowrap' }}>资金</span>
            <Form.Item name="cash" style={{ marginBottom: 0 }}>
              <InputNumber
                size="small"
                min={10000}
                style={{ width: 100 }}
                formatter={value => `${value}`.replace(/\B(?=(\d{3})+(?!\d))/g, ',')}
              />
            </Form.Item>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <span style={{ fontSize: 12, whiteSpace: 'nowrap' }}>股数</span>
            <Form.Item name="stake" style={{ marginBottom: 0 }}>
              <InputNumber
                size="small"
                min={100}
                step={100}
                style={{ width: 80 }}
              />
            </Form.Item>
          </div>
        </div>

        <div style={{ display: 'flex', gap: 16, alignItems: 'center', flexWrap: 'wrap', marginBottom: 8 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <span style={{ fontSize: 12, whiteSpace: 'nowrap' }}>开始</span>
            <Form.Item name="startDate" style={{ marginBottom: 0 }}>
              <DatePicker size="small" placeholder="开始" format="YYYYMMDD" />
            </Form.Item>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <span style={{ fontSize: 12, whiteSpace: 'nowrap' }}>结束</span>
            <Form.Item name="endDate" style={{ marginBottom: 0 }}>
              <DatePicker size="small" placeholder="结束" format="YYYYMMDD" />
            </Form.Item>
          </div>
        </div>

        <div style={{ display: 'flex', gap: 16, alignItems: 'center', flexWrap: 'wrap', marginBottom: 8 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <span style={{ fontSize: 12, whiteSpace: 'nowrap' }}>策略</span>
            <Form.Item name="strategy" style={{ marginBottom: 0 }}>
              <Select size="small" style={{ width: 100 }} onChange={setSelectedStrategy}>
                {strategies.map(s => (
                  <Select.Option key={s.id} value={s.id}>{s.name}</Select.Option>
                ))}
              </Select>
            </Form.Item>
          </div>

          {strategyParams.map(p => (
            <div key={p.name} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <span style={{ fontSize: 12, whiteSpace: 'nowrap' }}>{p.label}</span>
              <Form.Item name={p.name} style={{ marginBottom: 0 }}>
                <InputNumber
                  size="small"
                  min={p.min || 1}
                  max={p.max || 1000}
                  step={p.step || 1}
                  style={{ width: 50 }}
                />
              </Form.Item>
            </div>
          ))}
        </div>

        {(loading || status === 'completed') && (
          <Progress
            percent={status === 'completed' ? 100 : progress}
            size="small"
            status={status === 'completed' ? 'success' : (paused ? 'exception' : 'active')}
            format={percent => paused ? `已暂停 ${percent}%` : `${percent}%`}
            style={{ marginTop: 4 }}
          />
        )}
      </Form>
      <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
        <Button type="primary" htmlType="submit" disabled={!canStart} style={{ flex: 1 }} onClick={() => form.submit()}>
          开始
        </Button>
        <Button
          type="primary"
          onClick={paused ? onResume : onPause}
          disabled={paused ? !canResume : !canPause}
          style={{ flex: 1, backgroundColor: paused ? '#52c41a' : '#faad14' }}
        >
          {paused ? '恢复' : '暂停'}
        </Button>
        <Button danger onClick={onStop} disabled={!canStop} style={{ flex: 1 }}>
          停止
        </Button>
      </div>
    </Card>
  )
}

export default BacktestForm
