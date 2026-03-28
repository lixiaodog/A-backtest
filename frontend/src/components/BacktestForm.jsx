import React, { useState } from 'react'
import { Form, Input, DatePicker, Select, Button, Card, InputNumber, Space } from 'antd'
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

function BacktestForm({ onSubmit, loading }) {
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
    })
  }

  const currentStrategyParams = strategies.find(s => s.value === selectedStrategy)?.params || []

  return (
    <Card size="small" title="参数设置" style={{ height: '100%', overflow: 'auto' }}>
      <Form
        form={form}
        layout="vertical"
        onFinish={handleFinish}
        initialValues={{
          stock: '600519',
          strategy: 'sma_cross',
          period: 'daily',
          cash: 1000000,
          fast: 10,
          slow: 30,
          rsi_period: 14,
        }}
      >
        <Form.Item label="股票代码" name="stock" rules={[{ required: true }]}>
          <Input placeholder="如: 600519" size="small" />
        </Form.Item>

        <Form.Item label="周期" name="period">
          <Select size="small">
            {periods.map(p => (
              <Select.Option key={p.value} value={p.value}>{p.label}</Select.Option>
            ))}
          </Select>
        </Form.Item>

        <Form.Item label="日期">
          <Space>
            <Form.Item name="startDate" noStyle>
              <DatePicker size="small" placeholder="开始" format="YYYYMMDD" />
            </Form.Item>
            <Form.Item name="endDate" noStyle>
              <DatePicker size="small" placeholder="结束" format="YYYYMMDD" />
            </Form.Item>
          </Space>
        </Form.Item>

        <Form.Item label="策略" name="strategy">
          <Select size="small" onChange={setSelectedStrategy}>
            {strategies.map(s => (
              <Select.Option key={s.value} value={s.value}>{s.label}</Select.Option>
            ))}
          </Select>
        </Form.Item>

        {currentStrategyParams.includes('fast') && (
          <Form.Item label="快速周期" name="fast">
            <InputNumber size="small" min={1} max={100} style={{ width: '100%' }} />
          </Form.Item>
        )}

        {currentStrategyParams.includes('slow') && (
          <Form.Item label="慢速周期" name="slow">
            <InputNumber size="small" min={1} max={200} style={{ width: '100%' }} />
          </Form.Item>
        )}

        {currentStrategyParams.includes('rsi_period') && (
          <Form.Item label="RSI周期" name="rsi_period">
            <InputNumber size="small" min={1} max={50} style={{ width: '100%' }} />
          </Form.Item>
        )}

        <Form.Item label="初始资金" name="cash">
          <InputNumber
            size="small"
            min={10000}
            style={{ width: '100%' }}
            formatter={value => `${value}`.replace(/\B(?=(\d{3})+(?!\d))/g, ',')}
          />
        </Form.Item>

        <Form.Item style={{ marginBottom: 0 }}>
          <Button type="primary" htmlType="submit" loading={loading} block>
            {loading ? '回测中...' : '开始回测'}
          </Button>
        </Form.Item>
      </Form>
    </Card>
  )
}

export default BacktestForm
