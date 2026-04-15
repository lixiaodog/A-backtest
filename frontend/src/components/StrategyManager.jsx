import React, { useState, useEffect } from 'react'
import { Table, Button, Card, Tag, Space, Modal, Form, Input, Select, Tooltip, message, Divider, Tabs, Collapse } from 'antd'
import { PlusOutlined, EditOutlined, DeleteOutlined, EyeOutlined, FileTextOutlined, CodeOutlined } from '@ant-design/icons'
import axios from 'axios'

const { Panel } = Collapse

function StrategyManager() {
  const [strategies, setStrategies] = useState([])
  const [templates, setTemplates] = useState([])
  const [loading, setLoading] = useState(false)
  const [modalVisible, setModalVisible] = useState(false)
  const [detailVisible, setDetailVisible] = useState(false)
  const [codeVisible, setCodeVisible] = useState(false)
  const [selectedStrategy, setSelectedStrategy] = useState(null)
  const [selectedTemplate, setSelectedTemplate] = useState(null)
  const [editingStrategy, setEditingStrategy] = useState(null)
  const [form] = Form.useForm()
  const [code, setCode] = useState('')

  useEffect(() => {
    loadStrategies()
    loadTemplates()
  }, [])

  const loadStrategies = async () => {
    setLoading(true)
    try {
      const res = await axios.get('http://localhost:5000/api/strategy-manager/list')
      setStrategies(res.data || [])
    } catch (err) {
      message.error('加载策略列表失败')
    } finally {
      setLoading(false)
    }
  }

  const loadTemplates = async () => {
    try {
      const res = await axios.get('http://localhost:5000/api/strategy-manager/templates')
      setTemplates(res.data || [])
    } catch (err) {
      console.error('Failed to load templates:', err)
    }
  }

  const handleCreate = () => {
    setEditingStrategy(null)
    form.resetFields()
    setModalVisible(true)
  }

  const handleEdit = (strategy) => {
    setEditingStrategy(strategy)
    form.setFieldsValue({
      name: strategy.name,
      description: strategy.description,
      params: strategy.params?.map(p => ({
        name: p.name,
        default: p.default,
        description: p.description,
        type: p.type
      }))
    })
    setModalVisible(true)
  }

  const handleViewDetail = async (strategy) => {
    setSelectedStrategy(strategy)
    setDetailVisible(true)
  }

  const handleViewCode = async (strategy) => {
    try {
      const res = await axios.get(`http://localhost:5000/api/strategy-manager/${strategy.id}/code`)
      setCode(res.data.code || '')
      setSelectedStrategy(strategy)
      setCodeVisible(true)
    } catch (err) {
      message.error('获取代码失败')
    }
  }

  const handleDelete = async (strategy) => {
    if (!strategy.is_custom) {
      message.error('内置策略不能删除')
      return
    }

    Modal.confirm({
      title: '确认删除',
      content: `确定要删除策略 "${strategy.name}" 吗？`,
      onOk: async () => {
        try {
          await axios.delete(`http://localhost:5000/api/strategy-manager/${strategy.id}`)
          message.success('删除成功')
          loadStrategies()
        } catch (err) {
          message.error('删除失败')
        }
      }
    })
  }

  const handleSubmit = async (values) => {
    try {
      if (editingStrategy) {
        await axios.put(`http://localhost:5000/api/strategy-manager/${editingStrategy.id}`, values)
        message.success('更新成功')
      } else {
        await axios.post('http://localhost:5000/api/strategy-manager', values)
        message.success('创建成功')
      }
      setModalVisible(false)
      loadStrategies()
    } catch (err) {
      message.error('操作失败')
    }
  }

  const handleSelectTemplate = (templateId) => {
    const template = templates.find(t => t.id === templateId)
    if (template) {
      setSelectedTemplate(template)
      form.setFieldsValue({
        name: '',
        description: '',
        source_code: template.source_code
      })
    }
  }

  const renderParamTooltip = (param) => {
    return (
      <div style={{ fontSize: 12 }}>
        <div><strong>参数:</strong> {param.name}</div>
        <div><strong>默认值:</strong> {param.default}</div>
        <div><strong>类型:</strong> {param.type}</div>
        <div><strong>说明:</strong> {param.description}</div>
      </div>
    )
  }

  const columns = [
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
      render: (name, record) => (
        <Space>
          <span>{name}</span>
          {record.is_custom && <Tag color="blue">自定义</Tag>}
        </Space>
      )
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true
    },
    {
      title: '参数',
      key: 'params',
      render: (_, record) => (
        <span style={{ fontSize: 12, color: '#888' }}>
          {record.params?.length || 0} 个参数
        </span>
      )
    },
    {
      title: '操作',
      key: 'action',
      width: 200,
      render: (_, record) => (
        <Space>
          <Tooltip title="查看详情">
            <Button size="small" icon={<EyeOutlined />} onClick={() => handleViewDetail(record)} />
          </Tooltip>
          <Tooltip title="查看代码">
            <Button size="small" icon={<CodeOutlined />} onClick={() => handleViewCode(record)} />
          </Tooltip>
          {record.is_custom && (
            <>
              <Tooltip title="编辑">
                <Button size="small" icon={<EditOutlined />} onClick={() => handleEdit(record)} />
              </Tooltip>
              <Tooltip title="删除">
                <Button size="small" danger icon={<DeleteOutlined />} onClick={() => handleDelete(record)} />
              </Tooltip>
            </>
          )}
        </Space>
      )
    }
  ]

  return (
    <Card
      size="small"
      title={<><FileTextOutlined /> 策略管理器</>}
      extra={
        <Button type="primary" icon={<PlusOutlined />} onClick={handleCreate}>
          新建策略
        </Button>
      }
      style={{ height: '100%', overflow: 'auto' }}
    >
      <Tabs defaultActiveKey="strategies">
        <Tabs.TabPane tab="策略列表" key="strategies">
          <Table
            size="small"
            dataSource={strategies}
            columns={columns}
            rowKey="id"
            loading={loading}
            pagination={false}
            scroll={{ y: 300 }}
          />
        </Tabs.TabPane>

        <Tabs.TabPane tab="模板说明" key="templates">
          <Collapse accordion>
            {templates.map(template => (
              <Panel header={template.name} key={template.id}>
                <pre style={{ maxHeight: 400, overflow: 'auto', fontSize: 12, background: '#f5f5f5', padding: 8 }}>
                  {template.source_code}
                </pre>
              </Panel>
            ))}
          </Collapse>
        </Tabs.TabPane>
      </Tabs>

      <Modal
        title={editingStrategy ? '编辑策略' : '新建策略'}
        open={modalVisible}
        onCancel={() => setModalVisible(false)}
        footer={null}
        width={700}
      >
        <Tabs>
          <Tabs.TabPane tab="基本信息" key="basic">
            <Form form={form} layout="vertical" onFinish={handleSubmit}>
              <Form.Item name="name" label="策略名称" rules={[{ required: true }]}>
                <Input placeholder="输入策略名称" />
              </Form.Item>

              <Form.Item name="description" label="策略描述">
                <Input.TextArea rows={3} placeholder="输入策略描述" />
              </Form.Item>

              <Form.Item name="template_id" label="基于模板创建">
                <Select
                  placeholder="选择模板（可选）"
                  allowClear
                  onChange={handleSelectTemplate}
                >
                  {templates.map(t => (
                    <Select.Option key={t.id} value={t.id}>{t.name}</Select.Option>
                  ))}
                </Select>
              </Form.Item>

              <Form.Item name="source_code" label="源代码" hidden>
                <Input.TextArea rows={10} />
              </Form.Item>

              <Divider>参数定义</Divider>

              <Form.List name="params">
                {(fields, { add, remove }) => (
                  <>
                    {fields.map(({ key, name, ...restField }) => (
                      <Card key={key} size="small" style={{ marginBottom: 8 }}>
                        <Space align="start">
                          <Form.Item {...restField} name={[name, 'name']} label="参数名" rules={[{ required: true }]} style={{ marginBottom: 0 }}>
                            <Input placeholder="如: period" style={{ width: 100 }} />
                          </Form.Item>
                          <Form.Item {...restField} name={[name, 'default']} label="默认值" rules={[{ required: true }]} style={{ marginBottom: 0 }}>
                            <Input type="number" placeholder="如: 14" style={{ width: 80 }} />
                          </Form.Item>
                          <Form.Item {...restField} name={[name, 'type']} label="类型" style={{ marginBottom: 0 }}>
                            <Select style={{ width: 80 }}>
                              <Select.Option value="int">int</Select.Option>
                              <Select.Option value="float">float</Select.Option>
                            </Select>
                          </Form.Item>
                          <Form.Item {...restField} name={[name, 'description']} label="说明" rules={[{ required: true }]} style={{ marginBottom: 0, flex: 1 }}>
                            <Input placeholder="参数作用说明" />
                          </Form.Item>
                          <Button type="text" danger onClick={() => remove(name)}>删除</Button>
                        </Space>
                      </Card>
                    ))}
                    <Button type="dashed" onClick={() => add()} block>
                      + 添加参数
                    </Button>
                  </>
                )}
              </Form.List>

              <Form.Item style={{ marginTop: 16 }}>
                <Space>
                  <Button type="primary" htmlType="submit">
                    {editingStrategy ? '更新' : '创建'}
                  </Button>
                  <Button onClick={() => setModalVisible(false)}>取消</Button>
                </Space>
              </Form.Item>
            </Form>
          </Tabs.TabPane>

          {selectedTemplate && (
            <Tabs.TabPane tab="模板预览" key="preview">
              <pre style={{ maxHeight: 500, overflow: 'auto', fontSize: 12, background: '#f5f5f5', padding: 16 }}>
                {selectedTemplate.source_code}
              </pre>
            </Tabs.TabPane>
          )}
        </Tabs>
      </Modal>

      <Modal
        title="策略详情"
        open={detailVisible}
        onCancel={() => setDetailVisible(false)}
        footer={null}
        width={600}
      >
        {selectedStrategy && (
          <div>
            <h3>{selectedStrategy.name}</h3>
            <p style={{ color: '#666' }}>{selectedStrategy.description}</p>

            <Divider>参数说明</Divider>

            {selectedStrategy.params?.map((param, index) => (
              <Tooltip key={index} title={renderParamTooltip(param)} placement="left">
                <Card size="small" style={{ marginBottom: 8, cursor: 'help' }}>
                  <Space>
                    <Tag color="blue">{param.name}</Tag>
                    <span>默认值: <strong>{param.default}</strong></span>
                    <span>类型: <strong>{param.type}</strong></span>
                  </Space>
                  <div style={{ marginTop: 4, fontSize: 12, color: '#888' }}>
                    {param.description}
                  </div>
                </Card>
              </Tooltip>
            ))}
          </div>
        )}
      </Modal>

      <Modal
        title="策略代码"
        open={codeVisible}
        onCancel={() => setCodeVisible(false)}
        footer={null}
        width={800}
      >
        <pre style={{ maxHeight: 500, overflow: 'auto', fontSize: 12, background: '#1e1e1e', color: '#d4d4d4', padding: 16 }}>
          {code}
        </pre>
      </Modal>
    </Card>
  )
}

export default StrategyManager
