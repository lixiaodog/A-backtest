import React from 'react'
import { Card, Progress, List, Typography } from 'antd'

const { Text } = Typography

function StatusLog({ status, progress, message, result }) {
  const statusMap = {
    pending: { color: 'default', text: '等待中' },
    fetching_data: { color: 'processing', text: '获取数据' },
    data_loaded: { color: 'success', text: '数据加载完成' },
    running: { color: 'processing', text: '回测进行中' },
    completed: { color: 'success', text: '已完成' },
    failed: { color: 'error', text: '失败' },
  }

  const currentStatus = statusMap[status] || statusMap.pending

  const logs = []
  if (message) {
    logs.push(message)
  }

  return (
    <Card
      size="small"
      title="状态"
      extra={<Text type={status === 'failed' ? 'danger' : status === 'completed' ? 'success' : 'secondary'}>{currentStatus.text}</Text>}
      style={{ height: '100%' }}
    >
      <Progress
        percent={progress || 0}
        size="small"
        status={status === 'failed' ? 'exception' : status === 'completed' ? 'success' : 'active'}
      />
      {logs.length > 0 && (
        <List
          size="small"
          dataSource={logs}
          renderItem={(item, index) => (
            <List.Item key={index} style={{ padding: '4px 0' }}>
              <Text code style={{ fontSize: 12 }}>{item}</Text>
            </List.Item>
          )}
        />
      )}
    </Card>
  )
}

export default StatusLog
