import React from 'react'
import { Card, Table, Tag } from 'antd'

function TradeHistory({ trades }) {
  const columns = [
    {
      title: '时间',
      dataIndex: 'date',
      key: 'date',
      width: 120,
      render: (date) => {
        if (typeof date === 'number') {
          const d = new Date(date * 1000)
          return d.toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' })
        }
        return date
      },
    },
    {
      title: '方向',
      dataIndex: 'type',
      key: 'type',
      width: 70,
      render: (type) => (
        <Tag color={type === 'buy' ? 'green' : 'red'}>
          {type === 'buy' ? '买入' : '卖出'}
        </Tag>
      ),
    },
    {
      title: '成交价',
      dataIndex: 'price',
      key: 'price',
      width: 90,
      render: (price) => price?.toFixed(2),
    },
    {
      title: '数量',
      dataIndex: 'size',
      key: 'size',
      width: 70,
    },
    {
      title: '成交额',
      dataIndex: 'value',
      key: 'value',
      width: 100,
      render: (value) => value?.toFixed(2),
    },
    {
      title: '手续费',
      dataIndex: 'commission',
      key: 'commission',
      width: 80,
      render: (comm) => comm?.toFixed(2),
    },
  ]

  if (!trades || trades.length === 0) {
    return (
      <Card size="small" title="交易记录" style={{ height: '100%' }}>
        <p style={{ textAlign: 'center', color: '#999' }}>暂无交易记录</p>
      </Card>
    )
  }

  return (
    <Card size="small" title={`交易记录 (${trades.length}笔)`} style={{ height: '100%', overflow: 'auto' }}>
      <Table
        dataSource={trades}
        columns={columns}
        rowKey={(record, index) => index}
        pagination={false}
        size="small"
        scroll={{ y: 200 }}
      />
    </Card>
  )
}

export default TradeHistory
