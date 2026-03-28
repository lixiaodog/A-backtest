import React, { useRef, useEffect } from 'react'
import { Card, Typography } from 'antd'

const { Text } = Typography

function LogOutput({ logs }) {
  const scrollRef = useRef(null)

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [logs])

  return (
    <Card
      size="small"
      title="回测日志"
      style={{ height: '100%', display: 'flex', flexDirection: 'column' }}
      bodyStyle={{ flex: 1, overflow: 'auto', padding: 8 }}
    >
      <div
        ref={scrollRef}
        style={{
          fontFamily: 'monospace',
          fontSize: 12,
          lineHeight: 1.6,
          color: '#00ff00',
          background: '#0d1117',
          padding: 8,
          borderRadius: 4,
          height: '100%',
          overflow: 'auto'
        }}
      >
        {logs.map((log, i) => (
          <div key={i}>{log}</div>
        ))}
        {logs.length === 0 && (
          <Text type="secondary">等待回测开始...</Text>
        )}
      </div>
    </Card>
  )
}

export default LogOutput
