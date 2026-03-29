import React, { useState } from 'react'
import { Form, Input, DatePicker, Select, Button, Card, InputNumber, Progress } from 'antd'
import dayjs from 'dayjs'

const strategies = [
  { value: 'sma_cross', label: '双均线', params: ['fast', 'slow'] },
  { value: 'momentum', label: '动量', params: [] },
  { value: 'rsi', label: 'RSI', params: ['rsi_period'] },
]

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

function BacktestForm({ onSubmit, loading, progress = 0, status, paused, onPause, onResume }) {
  const [form] = Form.useForm()
  const [selectedStrategy, setSelectedStrategy] = useState('sma_cross')

  const handleFinish = (values) => {
    const params = {}

    if (values.fast) params.fast = values.fast
    if (values.slow) params.slow = values.slow
    if (values.rsi_period) params.rsi_period = values.rsi_period

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

  const currentStrategyParams = strategies.find(s => s.value === selectedStrategy)?.params || []

  return (
    <Card size="small" title="参数设置" style={{ height: '100%', overflow: 'auto' }}>
      <Form
        form={form}
        layout="inline"
        onFinish={handleFinish}
        initialValues={{
          stock: '600519',
          strategy: 'sma_cross',
          period: 'daily',
          cash: 1000000,
          stake: 100,
          fast: 10,
          slow: 30,
          rsi_period: 14,
        }}
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
              <Select size="small" style={{ width: 80 }} onChange={setSelectedStrategy}>
                {strategies.map(s => (
                  <Select.Option key={s.value} value={s.value}>{s.label}</Select.Option>
                ))}
              </Select>
            </Form.Item>
          </div>

          {currentStrategyParams.includes('fast') && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <span style={{ fontSize: 12, whiteSpace: 'nowrap' }}>快速</span>
              <Form.Item name="fast" style={{ marginBottom: 0 }}>
                <InputNumber size="small" min={1} max={100} style={{ width: 50 }} />
              </Form.Item>
            </div>
          )}

          {currentStrategyParams.includes('slow') && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <span style={{ fontSize: 12, whiteSpace: 'nowrap' }}>慢速</span>
              <Form.Item name="slow" style={{ marginBottom: 0 }}>
                <InputNumber size="small" min={1} max={200} style={{ width: 50 }} />
              </Form.Item>
            </div>
          )}

          {currentStrategyParams.includes('rsi_period') && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <span style={{ fontSize: 12, whiteSpace: 'nowrap' }}>RSI</span>
              <Form.Item name="rsi_period" style={{ marginBottom: 0 }}>
                <InputNumber size="small" min={1} max={50} style={{ width: 50 }} />
              </Form.Item>
            </div>
          )}
        </div>

        {paused ? (
          <Button type="primary" onClick={onResume} block style={{ backgroundColor: '#52c41a' }}>
            恢复回测
          </Button>
        ) : loading ? (
          <Button type="primary" onClick={onPause} block style={{ backgroundColor: '#faad14' }}>
            暂停回测
          </Button>
        ) : (
          <Button type="primary" htmlType="submit" loading={loading} block>
            开始回测
          </Button>
        )}

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
    </Card>
  )
}

export default BacktestForm
