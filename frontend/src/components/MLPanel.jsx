import React, { useState, useEffect } from 'react'
import { Form, DatePicker, Select, Button, Card, Checkbox, Progress, Table, Tag, Tabs, Space, message, AutoComplete } from 'antd'
import { RobotOutlined, DeleteOutlined, PlayCircleOutlined, CloudUploadOutlined, ExperimentOutlined } from '@ant-design/icons'
import axios from 'axios'

function MLPanel() {
  const [stocks, setStocks] = useState([])
  const [loading, setLoading] = useState(false)
  const [training, setTraining] = useState(false)
  const [progress, setProgress] = useState(0)
  const [models, setModels] = useState([])
  const [technicalFeatures, setTechnicalFeatures] = useState([])
  const [alphaFeatures, setAlphaFeatures] = useState([])
  const [selectedFeatures, setSelectedFeatures] = useState([])
  const [featureType, setFeatureType] = useState('all')
  const [trainingLogs, setTrainingLogs] = useState([])
  const [predictionResult, setPredictionResult] = useState(null)
  const [form] = Form.useForm()

  useEffect(() => {
    loadModels()
    loadTechnicalFeatures()
    loadAlphaFeatures()
    loadStocks()
  }, [])

  const loadStocks = async () => {
    try {
      const res = await axios.get('http://localhost:5000/api/ml/stocks')
      setStocks(res.data || [])
    } catch (err) {
      console.error('Failed to load stocks:', err)
    }
  }

  const loadModels = async () => {
    try {
      const res = await axios.get('http://localhost:5000/api/ml/models')
      setModels(res.data || [])
    } catch (err) {
      console.error('Failed to load models:', err)
    }
  }

  const loadTechnicalFeatures = async () => {
    try {
      const res = await axios.get('http://localhost:5000/api/ml/features?type=technical')
      setTechnicalFeatures(res.data || [])
    } catch (err) {
      console.error('Failed to load technical features:', err)
    }
  }

  const loadAlphaFeatures = async () => {
    try {
      const res = await axios.get('http://localhost:5000/api/ml/features?type=alpha191')
      setAlphaFeatures(res.data || [])
    } catch (err) {
      console.error('Failed to load alpha features:', err)
    }
  }

  const getCurrentFeatures = () => {
    if (featureType === 'technical') return technicalFeatures
    if (featureType === 'alpha191') return alphaFeatures
    return [...technicalFeatures, ...alphaFeatures]
  }

  const handleFeatureTypeChange = (type) => {
    setFeatureType(type)
    setSelectedFeatures([])
    form.setFieldsValue({ features: [] })
  }

  const handleTrain = async (values) => {
    if (selectedFeatures.length === 0) {
      message.error('请至少选择一个特征')
      return
    }
    setTraining(true)
    setProgress(0)
    setPredictionResult(null)

    const logEntry = {
      id: Date.now(),
      time: new Date().toLocaleString(),
      stock: values.stock,
      model: 'RandomForest',
      features: selectedFeatures.length,
      status: '训练中...'
    }
    setTrainingLogs(prev => [logEntry, ...prev])

    try {
      const res = await axios.post('http://localhost:5000/api/ml/train', {
        stock: values.stock,
        start_date: values.startDate ? values.startDate.format('YYYYMMDD') : '20240101',
        end_date: values.endDate ? values.endDate.format('YYYYMMDD') : '20260401',
        features: selectedFeatures,
        model_type: 'RandomForest',
        test_size: 0.2
      })

      setTrainingLogs(prev => prev.map(log =>
        log.id === logEntry.id
          ? { ...log, status: '完成', accuracy: res.data.accuracy, model_id: res.data.model_id }
          : log
      ))
      message.success('训练完成!')
      loadModels()
      setProgress(100)
    } catch (err) {
      setTrainingLogs(prev => prev.map(log =>
        log.id === logEntry.id
          ? { ...log, status: '失败: ' + (err.message || '未知错误') }
          : log
      ))
      message.error('训练失败: ' + (err.message || '未知错误'))
    } finally {
      setTraining(false)
    }
  }

  const handleIncrementalTrain = async (values) => {
    if (selectedFeatures.length === 0) {
      message.error('请至少选择一个特征')
      return
    }
    const modelId = values.base_model
    if (!modelId) {
      message.error('请选择基座模型')
      return
    }

    setTraining(true)
    setProgress(0)

    const logEntry = {
      id: Date.now(),
      time: new Date().toLocaleString(),
      stock: values.stock,
      model: 'RandomForest(增量)',
      features: selectedFeatures.length,
      status: '增量训练中...'
    }
    setTrainingLogs(prev => [logEntry, ...prev])

    try {
      const res = await axios.post('http://localhost:5000/api/ml/train/incremental', {
        stock: values.stock,
        start_date: values.startDate ? values.startDate.format('YYYYMMDD') : '20240101',
        end_date: values.endDate ? values.endDate.format('YYYYMMDD') : '20260401',
        features: selectedFeatures,
        model_id: modelId
      })

      setTrainingLogs(prev => prev.map(log =>
        log.id === logEntry.id
          ? { ...log, status: '完成', accuracy: res.data.accuracy, model_id: res.data.model_id }
          : log
      ))
      message.success('增量训练完成!')
      loadModels()
      setProgress(100)
    } catch (err) {
      setTrainingLogs(prev => prev.map(log =>
        log.id === logEntry.id
          ? { ...log, status: '失败: ' + (err.message || '未知错误') }
          : log
      ))
      message.error('增量训练失败')
    } finally {
      setTraining(false)
    }
  }

  const handlePredict = async (values) => {
    if (!values.model_id) {
      message.error('请选择模型')
      return
    }

    setLoading(true)
    setPredictionResult(null)

    try {
      const res = await axios.post('http://localhost:5000/api/ml/predict', {
        stock: values.stock,
        model_id: values.model_id,
        features: selectedFeatures
      })

      setPredictionResult(res.data)
      message.success('预测完成!')
    } catch (err) {
      message.error('预测失败: ' + (err.message || '未知错误'))
    } finally {
      setLoading(false)
    }
  }

  const handleDeleteModel = async (modelId) => {
    try {
      await axios.delete(`http://localhost:5000/api/ml/models/${modelId}`)
      message.success('模型已删除')
      loadModels()
    } catch (err) {
      message.error('删除失败')
    }
  }

  const getSignalColor = (signal) => {
    if (signal === '买入') return 'green'
    if (signal === '卖出') return 'red'
    return 'gray'
  }

  const currentFeatures = getCurrentFeatures()

  return (
    <Card
      size="small"
      title={<><RobotOutlined /> 机器学习</>}
      style={{ height: '100%', overflow: 'auto' }}
    >
      <Tabs defaultActiveKey="1" size="small">
        <Tabs.TabPane tab="训练" key="1">
          <Form form={form} layout="vertical" onFinish={handleTrain}>
            <Space direction="vertical" style={{ width: '100%' }}>
              <Form.Item name="stock" label="股票" rules={[{ required: true }]} style={{ marginBottom: 8 }}>
                <Select showSearch allowClear placeholder="选择股票">
                  {stocks.map(s => (
                    <Select.Option key={s} value={s}>{s}</Select.Option>
                  ))}
                </Select>
              </Form.Item>

              <div style={{ display: 'flex', gap: 8 }}>
                <Form.Item name="startDate" label="开始" style={{ flex: 1, marginBottom: 0 }}>
                  <DatePicker placeholder="开始日期" format="YYYYMMDD" />
                </Form.Item>
                <Form.Item name="endDate" label="结束" style={{ flex: 1, marginBottom: 0 }}>
                  <DatePicker placeholder="结束日期" format="YYYYMMDD" />
                </Form.Item>
              </div>

              <div>
                <div style={{ marginBottom: 8, color: '#888' }}>特征类型</div>
                <Space>
                  <Button.Group>
                    <Button type={featureType === 'all' ? 'primary' : 'default'} onClick={() => handleFeatureTypeChange('all')}>全部</Button>
                    <Button type={featureType === 'technical' ? 'primary' : 'default'} onClick={() => handleFeatureTypeChange('technical')}>技术指标</Button>
                    <Button type={featureType === 'alpha191' ? 'primary' : 'default'} onClick={() => handleFeatureTypeChange('alpha191')}>Alpha191</Button>
                  </Button.Group>
                  <span style={{ color: '#888', fontSize: 12 }}>已选: {selectedFeatures.length}</span>
                </Space>
              </div>

              <Form.Item name="features" label={`特征 (${currentFeatures.length})`} style={{ marginBottom: 8 }}>
                <Checkbox.Group value={selectedFeatures} onChange={(vals) => {
                  setSelectedFeatures(vals)
                  form.setFieldsValue({ features: vals })
                }}>
                  <div style={{ maxHeight: 150, overflow: 'auto', border: '1px solid #333', borderRadius: 4, padding: 8 }}>
                    {currentFeatures.map(f => (
                      <Checkbox key={f} value={f} style={{ width: '45%', marginLeft: 4 }}>{f}</Checkbox>
                    ))}
                  </div>
                </Checkbox.Group>
              </Form.Item>

              <div style={{ display: 'flex', gap: 8 }}>
                <Button
                  type="link"
                  size="small"
                  onClick={() => {
                    if (featureType === 'alpha191') {
                      setSelectedFeatures(alphaFeatures.slice(0, 30))
                      form.setFieldsValue({ features: alphaFeatures.slice(0, 30) })
                    } else if (featureType === 'technical') {
                      setSelectedFeatures(technicalFeatures)
                      form.setFieldsValue({ features: technicalFeatures })
                    } else {
                      setSelectedFeatures([...technicalFeatures, ...alphaFeatures.slice(0, 30)])
                      form.setFieldsValue({ features: [...technicalFeatures, ...alphaFeatures.slice(0, 30)] })
                    }
                  }}
                >
                  全选
                </Button>
                <Button type="link" size="small" onClick={() => { setSelectedFeatures([]); form.setFieldsValue({ features: [] }) }}>
                  清空
                </Button>
              </div>

              {training && <Progress percent={progress} size="small" status="active" />}

              <Button type="primary" htmlType="submit" icon={<PlayCircleOutlined />} loading={training} style={{ width: '100%' }}>
                开始训练
              </Button>
            </Space>
          </Form>
        </Tabs.TabPane>

        <Tabs.TabPane tab="增量训练" key="2">
          <Form layout="vertical" onFinish={handleIncrementalTrain}>
            <Space direction="vertical" style={{ width: '100%' }}>
              <Form.Item name="base_model" label="基座模型" rules={[{ required: true }]} style={{ marginBottom: 8 }}>
                <Select placeholder="选择基座模型">
                  {models.map(m => (
                    <Select.Option key={m.model_id} value={m.model_id}>
                      {m.stock} - {m.accuracy?.toFixed(2)} - {m.trained_at?.slice(0, 10)}
                    </Select.Option>
                  ))}
                </Select>
              </Form.Item>

              <Form.Item name="stock" label="股票" rules={[{ required: true }]} style={{ marginBottom: 0 }}>
                <Select showSearch allowClear placeholder="选择股票">
                  {stocks.map(s => (
                    <Select.Option key={s} value={s}>{s}</Select.Option>
                  ))}
                </Select>
              </Form.Item>

              <div style={{ display: 'flex', gap: 8 }}>
                <Form.Item name="startDate" style={{ flex: 1, marginBottom: 0 }}>
                  <DatePicker placeholder="新增数据开始" format="YYYYMMDD" />
                </Form.Item>
                <Form.Item name="endDate" style={{ flex: 1, marginBottom: 0 }}>
                  <DatePicker placeholder="新增数据结束" format="YYYYMMDD" />
                </Form.Item>
              </div>

              <div>
                <div style={{ marginBottom: 8, color: '#888' }}>特征类型</div>
                <Space>
                  <Button.Group>
                    <Button type={featureType === 'all' ? 'primary' : 'default'} onClick={() => handleFeatureTypeChange('all')}>全部</Button>
                    <Button type={featureType === 'technical' ? 'primary' : 'default'} onClick={() => handleFeatureTypeChange('technical')}>技术指标</Button>
                    <Button type={featureType === 'alpha191' ? 'primary' : 'default'} onClick={() => handleFeatureTypeChange('alpha191')}>Alpha191</Button>
                  </Button.Group>
                </Space>
              </div>

              <Form.Item name="features" label={`特征 (${selectedFeatures.length})`} style={{ marginBottom: 8 }}>
                <Checkbox.Group value={selectedFeatures} onChange={(vals) => {
                  setSelectedFeatures(vals)
                  form.setFieldsValue({ features: vals })
                }}>
                  <div style={{ maxHeight: 100, overflow: 'auto', border: '1px solid #333', borderRadius: 4, padding: 8 }}>
                    {currentFeatures.map(f => (
                      <Checkbox key={f} value={f} style={{ width: '45%', marginLeft: 4 }}>{f}</Checkbox>
                    ))}
                  </div>
                </Checkbox.Group>
              </Form.Item>

              <Button type="primary" htmlType="submit" icon={<CloudUploadOutlined />} loading={training} style={{ width: '100%' }}>
                增量训练
              </Button>
            </Space>
          </Form>
        </Tabs.TabPane>

        <Tabs.TabPane tab="预测" key="3">
          <Form layout="vertical" onFinish={handlePredict}>
            <Space direction="vertical" style={{ width: '100%' }}>
              <Form.Item name="model_id" label="模型" rules={[{ required: true }]} style={{ marginBottom: 8 }}>
                <Select placeholder="选择模型">
                  {models.map(m => (
                    <Select.Option key={m.model_id} value={m.model_id}>
                      {m.stock} - {m.accuracy?.toFixed(2)} - {m.trained_at?.slice(0, 10)}
                    </Select.Option>
                  ))}
                </Select>
              </Form.Item>

              <Form.Item name="stock" label="股票" rules={[{ required: true }]} style={{ marginBottom: 0 }}>
                <Select showSearch allowClear placeholder="选择股票">
                  {stocks.map(s => (
                    <Select.Option key={s} value={s}>{s}</Select.Option>
                  ))}
                </Select>
              </Form.Item>

              <Button type="primary" htmlType="submit" icon={<RobotOutlined />} loading={loading} style={{ width: '100%' }}>
                预测
              </Button>

              {predictionResult && (
                <div style={{ marginTop: 16, padding: 12, background: '#1a1a2e', borderRadius: 4 }}>
                  <div style={{ color: '#888', marginBottom: 8 }}>预测结果</div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
                    <Tag color={getSignalColor(predictionResult.signal)} style={{ fontSize: 16, padding: '4px 16px' }}>
                      {predictionResult.signal}
                    </Tag>
                    <span style={{ color: '#fff' }}>置信度: {(predictionResult.confidence * 100).toFixed(1)}%</span>
                  </div>
                  <div style={{ marginTop: 8, fontSize: 12, color: '#888' }}>
                    买入: {(predictionResult.probabilities?.buy || 0 * 100).toFixed(1)}% |
                    卖出: {(predictionResult.probabilities?.sell || 0).toFixed(1)}% |
                    持有: {(predictionResult.probabilities?.hold || 0).toFixed(1)}%
                  </div>
                </div>
              )}
            </Space>
          </Form>
        </Tabs.TabPane>

        <Tabs.TabPane tab="训练记录" key="4">
          <Table
            size="small"
            dataSource={trainingLogs}
            rowKey="id"
            pagination={false}
            scroll={{ y: 200 }}
            columns={[
              { title: '时间', dataIndex: 'time', width: 120 },
              { title: '股票', dataIndex: 'stock', width: 80 },
              { title: '模型', dataIndex: 'model', width: 100 },
              { title: '特征', dataIndex: 'features', width: 50 },
              {
                title: '状态',
                dataIndex: 'status',
                width: 100,
                render: status => {
                  if (status.includes('完成')) return <Tag color="green">{status}</Tag>
                  if (status.includes('失败')) return <Tag color="red">{status}</Tag>
                  return <Tag color="blue">{status}</Tag>
                }
              },
              { title: '准确率', dataIndex: 'accuracy', width: 70, render: v => v ? (v * 100).toFixed(1) + '%' : '-' }
            ]}
          />
        </Tabs.TabPane>

        <Tabs.TabPane tab="已训练模型" key="5">
          <Table
            size="small"
            dataSource={models}
            rowKey="model_id"
            pagination={false}
            scroll={{ y: 200 }}
            columns={[
              { title: '股票', dataIndex: 'stock', width: 80 },
              { title: '特征数', dataIndex: 'feature_count', width: 60 },
              { title: '准确率', dataIndex: 'accuracy', width: 70, render: v => v ? (v * 100).toFixed(1) + '%' : '-' },
              { title: '训练时间', dataIndex: 'trained_at', width: 120, render: v => v?.slice(0, 19) },
              {
                title: '操作',
                width: 60,
                render: (_, record) => (
                  <Button size="small" type="text" danger icon={<DeleteOutlined />} onClick={() => handleDeleteModel(record.model_id)} />
                )
              }
            ]}
          />
        </Tabs.TabPane>
      </Tabs>
    </Card>
  )
}

export default MLPanel