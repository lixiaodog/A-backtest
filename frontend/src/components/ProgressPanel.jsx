import React from 'react'
import { Card, Progress, Statistic, Row, Col, Table, Tag } from 'antd'

function ProgressPanel({ status, progress, result, message }) {
  const statusMap = {
    pending: { color: 'default', text: '等待中' },
    fetching_data: { color: 'processing', text: '获取数据' },
    data_loaded: { color: 'success', text: '数据加载完成' },
    running: { color: 'processing', text: '回测进行中' },
    completed: { color: 'success', text: '已完成' },
    failed: { color: 'error', text: '失败' },
  }

  const currentStatus = statusMap[status] || statusMap.pending

  const columns = [
    { title: '时间', dataIndex: 'date', key: 'date' },
    { title: '类型', dataIndex: 'type', key: 'type', render: (type) => (
      <Tag color={type === 'buy' ? 'green' : 'red'}>{type === 'buy' ? '买入' : '卖出'}</Tag>
    )},
    { title: '价格', dataIndex: 'price', key: 'price' },
    { title: '数量', dataIndex: 'size', key: 'size' },
  ]

  return (
    <Card title="回测进度">
      <Row gutter={16}>
        <Col span={8}>
          <Statistic title="状态" value={currentStatus.text} valueStyle={{ color: currentStatus.color === 'processing' ? '#1890ff' : currentStatus.color === 'success' ? '#52c41a' : currentStatus.color === 'error' ? '#ff4d4f' : '#999' }} />
        </Col>
        <Col span={16}>
          <Progress percent={progress || 0} status={status === 'failed' ? 'exception' : status === 'completed' ? 'success' : 'active'} />
          <p style={{ marginTop: 8, color: '#666' }}>{message || '等待开始...'}</p>
        </Col>
      </Row>

      {result && (
        <>
          <Row gutter={16} style={{ marginTop: 24 }}>
            <Col span={6}>
              <Statistic title="初始资金" value={result.initial_cash} precision={2} prefix="¥" />
            </Col>
            <Col span={6}>
              <Statistic title="最终资金" value={result.final_cash} precision={2} prefix="¥" />
            </Col>
            <Col span={6}>
              <Statistic title="总收益" value={result.total_return} precision={2} prefix="¥"
                valueStyle={{ color: result.total_return >= 0 ? '#52c41a' : '#ff4d4f' }} />
            </Col>
            <Col span={6}>
              <Statistic title="收益率" value={result.return_rate} precision={2} suffix="%"
                valueStyle={{ color: result.return_rate >= 0 ? '#52c41a' : '#ff4d4f' }} />
            </Col>
          </Row>
        </>
      )}
    </Card>
  )
}

export default ProgressPanel
