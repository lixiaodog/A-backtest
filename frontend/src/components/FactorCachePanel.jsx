import React, { useState, useEffect, useCallback } from 'react'
import { Card, Button, Table, Progress, Tag, Statistic, Row, Col, message, Space, Modal, Descriptions, Alert, Select, Switch, Input, Tooltip } from 'antd'
import { ReloadOutlined, DatabaseOutlined, PlayCircleOutlined, PauseCircleOutlined, CheckCircleOutlined, CloseCircleOutlined, SyncOutlined, SettingOutlined, StockOutlined } from '@ant-design/icons'
import axios from 'axios'

const { Option } = Select
const { TextArea } = Input

function FactorCachePanel() {
  const [loading, setLoading] = useState(false)
  const [statusLoading, setStatusLoading] = useState(false)
  const [cacheStatus, setCacheStatus] = useState(null)
  const [tasks, setTasks] = useState([])
  const [selectedTask, setSelectedTask] = useState(null)
  const [detailVisible, setDetailVisible] = useState(false)
  const [refreshInterval, setRefreshInterval] = useState(null)
  
  // 新增状态
  const [mode, setMode] = useState('thread')
  const [force, setForce] = useState(false)
  const [stockInput, setStockInput] = useState('')
  const [updateMode, setUpdateMode] = useState('all') // 'all' 或 'selected'
  const [configVisible, setConfigVisible] = useState(false)

  // 获取缓存状态
  const fetchCacheStatus = useCallback(async () => {
    setStatusLoading(true)
    try {
      const response = await axios.get('http://localhost:5000/api/factor-cache/status')
      setCacheStatus(response.data)
    } catch (error) {
      console.error('获取缓存状态失败:', error)
      message.error('刷新失败: ' + (error.response?.data?.error || error.message))
    } finally {
      setStatusLoading(false)
    }
  }, [])

  // 获取任务列表
  const fetchTasks = useCallback(async () => {
    try {
      const response = await axios.get('http://localhost:5000/api/factor-cache/tasks')
      setTasks(response.data.tasks || [])
    } catch (error) {
      console.error('获取任务列表失败:', error)
    }
  }, [])

  // 启动自动刷新（10秒间隔）
  const startAutoRefresh = useCallback(() => {
    if (refreshInterval) return
    const interval = setInterval(() => {
      fetchCacheStatus()
      fetchTasks()
    }, 10000)  // 10秒刷新一次
    setRefreshInterval(interval)
  }, [fetchCacheStatus, fetchTasks, refreshInterval])

  // 停止自动刷新
  const stopAutoRefresh = useCallback(() => {
    if (refreshInterval) {
      clearInterval(refreshInterval)
      setRefreshInterval(null)
    }
  }, [refreshInterval])

  // 初始加载和自动刷新
  useEffect(() => {
    fetchCacheStatus()
    fetchTasks()
    startAutoRefresh()

    return () => {
      stopAutoRefresh()
    }
  }, [fetchCacheStatus, fetchTasks, startAutoRefresh, stopAutoRefresh])

  // 触发缓存更新
  const handleUpdate = async () => {
    setLoading(true)
    try {
      const params = { mode, force }
      
      // 如果选择了指定股票
      if (updateMode === 'selected' && stockInput.trim()) {
        const stocks = stockInput.split(/[\n,]/)
          .map(s => s.trim())
          .filter(s => s)
          .map(s => {
            // 去除股票代码后缀（如 .SZ, .SH, .BJ）
            return s.replace(/\.(SZ|SH|BJ)$/i, '')
          })
        if (stocks.length === 0) {
          message.warning('请输入股票代码')
          setLoading(false)
          return
        }
        params.stocks = stocks
      }
      
      const response = await axios.post('http://localhost:5000/api/factor-cache/update', params)
      const { mode: respMode, type, stocks_count } = response.data
      const modeText = respMode === 'single' ? '单线程' : respMode === 'process' ? '多进程' : '多线程'
      const typeText = type === 'full' ? '全量' : '增量'
      message.success(`缓存更新任务已启动: ${response.data.task_id} (${modeText}模式, ${typeText}, ${stocks_count === 'all' ? '全部股票' : stocks_count + '只股票'})`)
      fetchTasks()
      setConfigVisible(false)
    } catch (error) {
      message.error('启动缓存更新失败: ' + (error.response?.data?.error || error.message))
    } finally {
      setLoading(false)
    }
  }

  // 停止任务
  const handleStopTask = async (taskId) => {
    try {
      await axios.post(`http://localhost:5000/api/factor-cache/tasks/${taskId}/stop`)
      message.success('任务已停止')
      fetchTasks()
    } catch (error) {
      message.error('停止任务失败: ' + (error.response?.data?.error || error.message))
    }
  }

  // 查看任务详情
  const handleViewDetail = (task) => {
    setSelectedTask(task)
    setDetailVisible(true)
  }

  // 删除已完成/失败的任务
  const handleDeleteTask = async (taskId) => {
    try {
      await axios.delete(`http://localhost:5000/api/factor-cache/tasks/${taskId}`)
      message.success('任务已删除')
      fetchTasks()
    } catch (error) {
      message.error('删除任务失败: ' + (error.response?.data?.error || error.message))
    }
  }

  // 任务状态标签
  const getStatusTag = (status) => {
    const statusMap = {
      pending: { color: 'default', icon: <PauseCircleOutlined />, text: '等待中' },
      running: { color: 'processing', icon: <SyncOutlined spin />, text: '运行中' },
      completed: { color: 'success', icon: <CheckCircleOutlined />, text: '已完成' },
      failed: { color: 'error', icon: <CloseCircleOutlined />, text: '失败' },
      stopped: { color: 'warning', icon: <CloseCircleOutlined />, text: '已停止' }
    }
    const config = statusMap[status] || statusMap.pending
    return <Tag icon={config.icon} color={config.color}>{config.text}</Tag>
  }

  // 任务列表列定义
  const taskColumns = [
    {
      title: '任务ID',
      dataIndex: 'task_id',
      key: 'task_id',
      width: 90,
      render: (id) => <span style={{ fontFamily: 'monospace', fontSize: 12 }}>{id}</span>
    },
    {
      title: '类型',
      dataIndex: 'type',
      key: 'type',
      width: 90,
      render: (type) => (
        <Tag color={type === 'full' ? 'blue' : 'green'} size="small">
          {type === 'full' ? '全量' : '增量'}
        </Tag>
      )
    },
    {
      title: '模式',
      dataIndex: 'mode',
      key: 'mode',
      width: 80,
      render: (mode) => {
        const modeMap = {
          'single': { text: '单线程', color: 'default' },
          'process': { text: '多进程', color: 'blue' },
          'thread': { text: '多线程', color: 'cyan' }
        }
        const config = modeMap[mode] || modeMap.thread
        return <Tag color={config.color} size="small">{config.text}</Tag>
      }
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status) => getStatusTag(status)
    },
    {
      title: '进度',
      dataIndex: 'progress',
      key: 'progress',
      width: 160,
      render: (progress, record) => (
        <Progress 
          percent={progress} 
          size="small" 
          status={record.status === 'failed' ? 'exception' : record.status === 'completed' ? 'success' : 'active'}
        />
      )
    },
    {
      title: '已处理',
      dataIndex: 'processed_count',
      key: 'processed_count',
      width: 100,
      render: (count, record) => `${count || 0} / ${record.total_count || 0}`
    },
    {
      title: '股票数',
      key: 'stocks_count',
      width: 80,
      render: (_, record) => {
        if (record.stocks && record.stocks.length > 0) {
          return <Tag size="small" color="orange">{record.stocks.length}</Tag>
        }
        return <Tag size="small">全部</Tag>
      }
    },
    {
      title: '开始时间',
      dataIndex: 'start_time',
      key: 'start_time',
      width: 160,
      render: (time) => time ? new Date(time).toLocaleString() : '-'
    },
    {
      title: '耗时',
      dataIndex: 'elapsed_time',
      key: 'elapsed_time',
      width: 80,
      render: (seconds) => {
        if (!seconds) return '-'
        if (seconds < 60) return `${Math.round(seconds)}秒`
        if (seconds < 3600) return `${Math.round(seconds / 60)}分钟`
        return `${Math.round(seconds / 3600 * 10) / 10}小时`
      }
    },
    {
      title: '消息',
      dataIndex: 'message',
      key: 'message',
      ellipsis: true
    },
    {
      title: '操作',
      key: 'action',
      width: 160,
      fixed: 'right',
      render: (_, record) => (
        
        <Space size="small">
          <Button size="small" onClick={() => handleViewDetail(record)}>
            详情
          </Button>
          {record.status === 'running' && (
            <Button size="small" danger onClick={() => handleStopTask(record.task_id)}>
              停止
            </Button>
          )}
          {(record.status === 'completed' || record.status === 'failed' || record.status === 'stopped') && (
            <Button size="small" onClick={() => handleDeleteTask(record.task_id)}>
              删除
            </Button>
          )}
        </Space>
      )
    }
  ]

  return (
    <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>
      {/* 缓存状态概览 */}
      <Card 
        title={<span><DatabaseOutlined /> 因子缓存状态</span>}
        extra={
          <Button icon={<ReloadOutlined />} loading={statusLoading} onClick={fetchCacheStatus}>
            刷新
          </Button>
        }
        style={{ marginBottom: 16 }}
      >
        {cacheStatus ? (
          <Row gutter={16}>
            <Col span={6}>
              <Statistic 
                title="股票数量" 
                value={cacheStatus.stock_count} 
                suffix="只"
              />
            </Col>
            <Col span={6}>
              <Statistic 
                title="总存储大小" 
                value={(cacheStatus.total_size_mb / 1024).toFixed(2)} 
                suffix="GB"
              />
            </Col>
            <Col span={6}>
              <Statistic 
                title="缓存覆盖率" 
                value={(cacheStatus.coverage * 100).toFixed(1)} 
                suffix="%"
                valueStyle={{ color: cacheStatus.coverage > 0.9 ? '#52c41a' : cacheStatus.coverage > 0.7 ? '#faad14' : '#ff4d4f' }}
              />
            </Col>
            <Col span={6}>
              <Statistic 
                title="活跃任务" 
                value={tasks.filter(t => t.status === 'running').length} 
                suffix="个"
              />
            </Col>
            {cacheStatus.libraries && (
              <Col span={24} style={{ marginTop: 16 }}>
                <Descriptions title="按因子库统计" bordered size="small">
                  {Object.entries(cacheStatus.libraries).map(([lib, stats]) => (
                    <Descriptions.Item key={lib} label={lib}>
                      {stats.factor_count} 个因子, {stats.stock_count} 只股票
                    </Descriptions.Item>
                  ))}
                </Descriptions>
              </Col>
            )}
          </Row>
        ) : (
          <Alert message="无法获取缓存状态，请确保后端服务已启动" type="warning" />
        )}
      </Card>

      {/* 操作按钮 */}
      <Card style={{ marginBottom: 16 }}>
        <Space size="middle">
          <Button 
            type="primary" 
            icon={<SyncOutlined />}
            loading={loading}
            onClick={() => setConfigVisible(true)}
          >
            更新缓存
          </Button>
          <Button 
            icon={<SettingOutlined />}
            onClick={() => setConfigVisible(true)}
          >
            配置选项
          </Button>
          <span style={{ color: '#888', marginLeft: 16 }}>
            上次更新: {cacheStatus?.last_update ? new Date(cacheStatus.last_update).toLocaleString() : '从未'}
          </span>
        </Space>
      </Card>

      {/* 任务列表 */}
      <Card title="任务列表">
        <Table 
          columns={taskColumns} 
          dataSource={tasks} 
          rowKey="task_id"
          pagination={{ pageSize: 10 }}
          size="small"
          locale={{ emptyText: '暂无任务' }}
          scroll={{ x: 1200 }}
        />
      </Card>

      {/* 配置弹窗 */}
      <Modal
        title="缓存更新配置"
        visible={configVisible}
        onOk={handleUpdate}
        onCancel={() => setConfigVisible(false)}
        okText="开始更新"
        cancelText="取消"
        confirmLoading={loading}
        width={600}
      >
        <Space direction="vertical" style={{ width: '100%' }} size="large">
          {/* 运行模式 */}
          <div>
            <div style={{ marginBottom: 8, fontWeight: 500 }}>运行模式</div>
            <Select value={mode} onChange={setMode} style={{ width: '100%' }}>
              <Option value="thread">
                <Space>
                  <span>多线程模式</span>
                  <span style={{ color: '#888', fontSize: 12 }}>- 默认，I/O密集型，推荐</span>
                </Space>
              </Option>
              <Option value="process">
                <Space>
                  <span>多进程模式</span>
                  <span style={{ color: '#888', fontSize: 12 }}>- CPU密集型，大量计算时使用</span>
                </Space>
              </Option>
              <Option value="single">
                <Space>
                  <span>单线程模式</span>
                  <span style={{ color: '#888', fontSize: 12 }}>- 调试使用</span>
                </Space>
              </Option>
            </Select>
          </div>

          {/* 强制重新生成 */}
          <div>
            <div style={{ marginBottom: 8, fontWeight: 500 }}>更新方式</div>
            <Space direction="vertical" style={{ width: '100%' }}>
              <Switch
                checked={force}
                onChange={setForce}
                checkedChildren="强制全量重新生成"
                unCheckedChildren="智能增量更新"
              />
              <div style={{ color: '#888', fontSize: 12 }}>
                {force 
                  ? '⚠️ 将删除现有缓存并重新生成所有因子数据，耗时较长' 
                  : '✓ 仅更新新增或变更的数据，速度更快'}
              </div>
            </Space>
          </div>

          {/* 股票选择 */}
          <div>
            <div style={{ marginBottom: 8, fontWeight: 500 }}>更新范围</div>
            <Select value={updateMode} onChange={setUpdateMode} style={{ width: '100%', marginBottom: 8 }}>
              <Option value="all">全部股票</Option>
              <Option value="selected">指定股票</Option>
            </Select>
            
            {updateMode === 'selected' && (
              <>
                <TextArea
                  value={stockInput}
                  onChange={(e) => setStockInput(e.target.value)}
                  placeholder="请输入股票代码，多个股票用逗号或换行分隔&#10;例如：000001.SZ, 600000.SH"
                  rows={4}
                />
                <div style={{ marginTop: 8, color: '#888', fontSize: 12 }}>
                  <StockOutlined /> 已输入 {stockInput.split(/[\n,]/).map(s => s.trim()).filter(s => s).length} 只股票
                </div>
              </>
            )}
          </div>
        </Space>
      </Modal>

      {/* 任务详情弹窗 */}
      <Modal
        title="任务详情"
        visible={detailVisible}
        onCancel={() => setDetailVisible(false)}
        footer={[
          <Button key="close" onClick={() => setDetailVisible(false)}>
            关闭
          </Button>
        ]}
        width={700}
      >
        {selectedTask && (
          <Descriptions bordered column={2} size="small">
            <Descriptions.Item label="任务ID">{selectedTask.task_id}</Descriptions.Item>
            <Descriptions.Item label="任务类型">
              <Tag color={selectedTask.type === 'full' ? 'blue' : 'green'}>
                {selectedTask.type === 'full' ? '全量更新' : '增量更新'}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="运行模式">
              <Tag color={selectedTask.mode === 'process' ? 'blue' : selectedTask.mode === 'single' ? 'default' : 'cyan'}>
                {selectedTask.mode === 'single' ? '单线程' : selectedTask.mode === 'process' ? '多进程' : '多线程'}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="状态">{getStatusTag(selectedTask.status)}</Descriptions.Item>
            <Descriptions.Item label="进度">{selectedTask.progress}%</Descriptions.Item>
            <Descriptions.Item label="已处理">{selectedTask.processed_count} / {selectedTask.total_count}</Descriptions.Item>
            <Descriptions.Item label="成功数">{selectedTask.success_count || 0}</Descriptions.Item>
            <Descriptions.Item label="失败数">{selectedTask.fail_count || 0}</Descriptions.Item>
            {selectedTask.stocks && selectedTask.stocks.length > 0 && (
              <Descriptions.Item label="指定股票" span={2}>
                <div style={{ maxHeight: 100, overflow: 'auto' }}>
                  {selectedTask.stocks.map((stock, idx) => (
                    <Tag key={idx} size="small" style={{ margin: 2 }}>{stock}</Tag>
                  ))}
                </div>
              </Descriptions.Item>
            )}
            <Descriptions.Item label="开始时间">
              {selectedTask.start_time ? new Date(selectedTask.start_time).toLocaleString() : '-'}
            </Descriptions.Item>
            <Descriptions.Item label="结束时间">
              {selectedTask.end_time ? new Date(selectedTask.end_time).toLocaleString() : '-'}
            </Descriptions.Item>
            <Descriptions.Item label="耗时">
              {selectedTask.elapsed_time ? `${Math.round(selectedTask.elapsed_time)}秒` : '-'}
            </Descriptions.Item>
            <Descriptions.Item label="当前股票">{selectedTask.current_stock || '-'}</Descriptions.Item>
            <Descriptions.Item label="消息" span={2}>{selectedTask.message || '-'}</Descriptions.Item>
            {selectedTask.error && (
              <Descriptions.Item label="错误信息" span={2}>
                <Alert message={selectedTask.error} type="error" />
              </Descriptions.Item>
            )}
          </Descriptions>
        )}
      </Modal>
    </div>
  )
}

export default FactorCachePanel