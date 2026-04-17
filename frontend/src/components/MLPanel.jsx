import React, { useState, useEffect } from 'react'
import { Form, DatePicker, Select, Button, Card, Checkbox, Progress, Table, Tag, Tabs, Space, message, Input, Switch, List, Divider } from 'antd'
import { RobotOutlined, DeleteOutlined, PlayCircleOutlined, CloudUploadOutlined, StopOutlined, PlusOutlined, ClearOutlined } from '@ant-design/icons'
import axios from 'axios'

function MLPanel() {
  const [markets, setMarkets] = useState(['SZ', 'SH', 'BJ'])
  const [periods, setPeriods] = useState(['1d', '1m', '5m', '15m', '30m', '60m', '1h', '4h', '1w'])
  const [selectedMarket, setSelectedMarket] = useState('SZ')
  const [selectedPeriod, setSelectedPeriod] = useState('1d')
  const [stocks, setStocks] = useState([])
  const [loading, setLoading] = useState(false)
  const [training, setTraining] = useState(false)
  const [currentTaskId, setCurrentTaskId] = useState(null)
  const [progress, setProgress] = useState(0)
  const [models, setModels] = useState([])
  const [ensembleGroups, setEnsembleGroups] = useState({})
  const [technicalFeatures, setTechnicalFeatures] = useState([])
  const [alphaFeatures, setAlphaFeatures] = useState([])
  const [selectedFeatures, setSelectedFeatures] = useState([])
  const [featureType, setFeatureType] = useState('all')
  const [modelType, setModelType] = useState('RandomForest')
  const [trainingLogs, setTrainingLogs] = useState([])
  const [predictionResult, setPredictionResult] = useState(null)

  // 任务队列状态
  const [taskQueue, setTaskQueue] = useState([])
  const [currentTaskIndex, setCurrentTaskIndex] = useState(-1)
  const [totalTasks, setTotalTasks] = useState(0)

  const [form] = Form.useForm()
  const useEnsemble = Form.useWatch('useEnsemble', form)

  const generateModelName = () => {
    const market = selectedMarket || 'SZ'
    const period = (selectedPeriod || '1d').toUpperCase()
    const trainMode = form.getFieldValue('mode') || 'classification'
    const model = useEnsemble ? 'ENS' : (form.getFieldValue('modelType') || 'RF')
    const now = new Date()
    const date = `${now.getFullYear()}${String(now.getMonth()+1).padStart(2,'0')}${String(now.getDate()).padStart(2,'0')}`
    const features = selectedFeatures.length || 0
    const horizon = form.getFieldValue('horizon') || 5
    const threshold = form.getFieldValue('threshold') || '0.02'
    const volWindow = form.getFieldValue('volWindow') || 20
    const modeStr = trainMode === 'regression' ? 'REG' : 'CLS'
    return `${market}_${period}_${model}_${date}_${features}f_${horizon}h_${threshold}t_${volWindow}v_${modeStr}`
  }

  useEffect(() => {
    loadModels()
    loadTechnicalFeatures()
    loadAlphaFeatures()
    loadMarkets()
    loadPeriods()
    loadStocks()
  }, [])

  useEffect(() => {
    if (form.getFieldValue('modelName') === undefined || form.getFieldValue('modelName') === '') {
      form.setFieldsValue({ modelName: generateModelName() })
    }
  }, [selectedMarket, selectedPeriod, useEnsemble, selectedFeatures])

  const loadMarkets = async () => {
    try {
      const res = await axios.get('http://localhost:5000/api/ml/markets')
      if (res.data && res.data.length > 0) {
        setMarkets(res.data)
        setSelectedMarket(res.data[0])
      }
    } catch (err) {
      console.error('Failed to load markets:', err)
    }
  }

  const loadPeriods = async (market) => {
    try {
      const res = await axios.get(`http://localhost:5000/api/ml/periods?market=${market || selectedMarket}`)
      if (res.data && res.data.length > 0) {
        setPeriods(res.data)
      }
    } catch (err) {
      console.error('Failed to load periods:', err)
    }
  }

  const loadStocks = async (market, period) => {
    try {
      const mkt = market || selectedMarket
      const prd = period || selectedPeriod
      const res = await axios.get(`http://localhost:5000/api/ml/stocks?market=${mkt}&period=${prd}`)
      setStocks(res.data || [])
    } catch (err) {
      console.error('Failed to load stocks:', err)
    }
  }

  const handleMarketChange = (market) => {
    setSelectedMarket(market)
    setSelectedPeriod('1d')
    loadPeriods(market)
    loadStocks(market, '1d')
  }

  const handlePeriodChange = (period) => {
    setSelectedPeriod(period)
    loadStocks(selectedMarket, period)
  }

  const loadModels = async () => {
    try {
      const res = await axios.get('http://localhost:5000/api/ml/models')
      const data = res.data || {}
      setModels(data.models || [])
      setEnsembleGroups(data.ensemble_groups || {})
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

  const handleStopTraining = async () => {
    if (!currentTaskId) return
    try {
      await axios.post(`http://localhost:5000/api/ml/train/stop/${currentTaskId}`)
      message.success('训练任务已停止')
    } catch (e) {
      message.error('停止训练失败: ' + (e.message || '未知错误'))
    }
    setTraining(false)
    setCurrentTaskId(null)
  }

  // 添加任务到队列
  const addTaskToQueue = () => {
    const values = form.getFieldsValue()

    if (selectedFeatures.length === 0) {
      message.error('请至少选择一个特征')
      return
    }

    let selectedStocks = values.stock || []
    if (selectedStocks.includes('__SELECT_ALL__')) {
      selectedStocks = stocks
    }

    if (selectedStocks.length === 0) {
      message.error('请至少选择一只股票')
      return
    }

    const stockDisplay = selectedStocks.length > 1 ? `${selectedStocks.length}只股票` : selectedStocks[0]

    const newTask = {
      id: `task_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      stock: selectedStocks,
      stockDisplay: stockDisplay,
      market: selectedMarket,
      period: selectedPeriod,
      model_name: values.modelName || null,
      end_date: values.endDate ? values.endDate.format('YYYYMMDD') : '',
      features: [...selectedFeatures],
      model_type: values.modelType || 'RandomForest',
      horizon: values.horizon ? parseInt(values.horizon) : 5,
      threshold: values.threshold ? parseFloat(values.threshold) / 100 : 0.02,
      label_type: values.labelType || 'fixed',
      vol_window: values.volWindow ? parseInt(values.volWindow) : 20,
      lower_q: 0.2,
      upper_q: 0.8,
      mode: values.mode || 'classification',
      use_ensemble: values.useEnsemble || false,
      test_size: 0.2,
      train_mode: values.trainMode || 'thread'
    }

    setTaskQueue(prev => [...prev, newTask])
    message.success(`已添加任务: ${stockDisplay}`)
  }

  // 从队列移除任务
  const removeTaskFromQueue = (taskId) => {
    setTaskQueue(prev => prev.filter(t => t.id !== taskId))
  }

  // 清空任务队列
  const clearTaskQueue = () => {
    setTaskQueue([])
    message.info('任务队列已清空')
  }

  // 提交任务队列进行训练
  const submitTaskQueue = async () => {
    if (taskQueue.length === 0) {
      message.error('任务队列为空，请先添加任务')
      return
    }

    // 保存任务数量（在清空前）
    const savedTaskCount = taskQueue.length

    setTraining(true)
    setProgress(0)
    setPredictionResult(null)
    setTotalTasks(savedTaskCount)
    setCurrentTaskIndex(0)

    // 添加日志记录
    const logEntry = {
      id: Date.now(),
      time: new Date().toLocaleString(),
      stock: `${savedTaskCount}个任务`,
      model: '批量训练',
      features: '-',
      status: '等待开始...',
      progress: 0,
      message: ''
    }
    setTrainingLogs(prev => [logEntry, ...prev])

    try {
      // 准备提交的任务列表（移除前端临时id）
      const tasksToSubmit = taskQueue.map(task => {
        const { id, stockDisplay, ...taskData } = task
        return taskData
      })

      const res = await axios.post('http://localhost:5000/api/ml/train/batch', {
        tasks: tasksToSubmit
      })

      const taskId = res.data.task_id
      setCurrentTaskId(taskId)
      setTrainingLogs(prev => prev.map(log =>
        log.id === logEntry.id
          ? { ...log, status: '训练中', task_id: taskId }
          : log
      ))

      // 清空任务队列
      setTaskQueue([])

      // 轮询进度
      const pollProgress = setInterval(async () => {
        try {
          const progressRes = await axios.get(`http://localhost:5000/api/ml/train/progress/${taskId}`)
          if (progressRes.data.status === 'unknown') {
            clearInterval(pollProgress)
            setTrainingLogs(prev => prev.map(log =>
              log.id === logEntry.id
                ? { ...log, status: '失败: 任务未找到' }
                : log
            ))
            setTraining(false)
            setCurrentTaskIndex(-1)
            return
          }

          const prog = progressRes.data.progress || 0
          const status = progressRes.data.status || '训练中'
          const currentIdx = progressRes.data.current_task_index || 0
          const total = progressRes.data.total_tasks || savedTaskCount

          setProgress(prog)
          setCurrentTaskIndex(currentIdx)
          setTotalTasks(total)

          setTrainingLogs(prev => prev.map(log =>
            log.id === logEntry.id
              ? { ...log, progress: prog, status: status, message: progressRes.data.message || '' }
              : log
          ))

          if (prog >= 100) {
            clearInterval(pollProgress)
            setTrainingLogs(prev => prev.map(log =>
              log.id === logEntry.id
                ? { ...log, status: '完成', progress: 100 }
                : log
            ))
            message.success('所有训练任务完成!')
            loadModels()
            setTraining(false)
            setCurrentTaskIndex(-1)
          }
        } catch (e) {
          clearInterval(pollProgress)
          setTrainingLogs(prev => prev.map(log =>
            log.id === logEntry.id
              ? { ...log, status: '失败: ' + e.message }
              : log
          ))
          setTraining(false)
          setCurrentTaskIndex(-1)
        }
      }, 1000)
    } catch (err) {
      setTrainingLogs(prev => prev.map(log =>
        log.id === logEntry.id
          ? { ...log, status: '失败: ' + (err.message || '未知错误') }
          : log
      ))
      message.error('训练失败: ' + (err.response?.data?.error || err.message || '未知错误'))
      setTraining(false)
      setCurrentTaskIndex(-1)
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
      model: '增量训练',
      features: selectedFeatures.length,
      status: '增量训练中...'
    }
    setTrainingLogs(prev => [logEntry, ...prev])

    try {
      const res = await axios.post('http://localhost:5000/api/ml/train/incremental', {
        stock: values.stock,
        end_date: values.endDate ? values.endDate.format('YYYYMMDD') : '',
        features: selectedFeatures,
        model_id: modelId
      })

      setTrainingLogs(prev => prev.map(log =>
        log.id === logEntry.id
          ? { ...log, status: '完成', model_id: res.data.model?.id }
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
      const stockInput = values.stock || ''
      const stocks = stockInput.split(',').map(s => s.trim()).filter(s => s)

      const res = await axios.post('http://localhost:5000/api/ml/predict', {
        stocks: stocks,
        model_id: values.model_id,
        period: values.period || '1d'
      })

      const results = res.data.results || []
      const successResults = results.filter(r => !r.error)
      const failedResults = results.filter(r => r.error)

      if (successResults.length === 1) {
        const fullResult = {
          ...successResults[0].prediction,
          stock_code: successResults[0].stock_code,
          stock_name: successResults[0].stock_name
        }
        setPredictionResult(fullResult)
      } else {
        setPredictionResult({
          batch_results: results,
          summary: {
            total: results.length,
            success: successResults.length,
            failed: failedResults.length
          }
        })
      }

      if (failedResults.length > 0) {
        message.warning(`${failedResults.length} 个股票预测失败`)
      } else {
        message.success('预测完成!')
      }
    } catch (err) {
      message.error('预测失败: ' + (err.response?.data?.error || err.message || '未知错误'))
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
    if (signal === '买入' || signal === '轻度买入' || signal === '强烈买入') return 'green'
    if (signal === '卖出' || signal === '轻度卖出' || signal === '强烈卖出') return 'red'
    return 'gray'
  }

  const renderPredictionResult = (result) => {
    if (!result) return null

    if (result.batch_results) {
      const { batch_results, summary } = result
      return (
        <div style={{ marginTop: 16, padding: 12, background: '#1a1a2e', borderRadius: 4 }}>
          <div style={{ color: '#888', marginBottom: 8 }}>
            批量预测结果 - 共 {summary.total} 个，成功 {summary.success} 个
          </div>
          <Table
            size="small"
            dataSource={batch_results}
            rowKey="stock_code"
            pagination={false}
            scroll={{ y: 300 }}
            columns={[
              { title: '股票', dataIndex: 'stock_code', width: 80 },
              {
                title: '信号',
                dataIndex: 'prediction',
                render: (pred) => {
                  if (!pred) return <Tag color="red">失败</Tag>
                  const signal = pred.signal
                  return <Tag color={getSignalColor(signal)}>{signal}</Tag>
                }
              },
              {
                title: '置信度',
                dataIndex: 'prediction',
                render: (pred) => {
                  if (!pred || pred.confidence == null) return '-'
                  return `${(pred.confidence * 100).toFixed(1)}%`
                }
              },
              {
                title: '说明',
                dataIndex: 'error',
                render: (err) => err ? <span style={{ color: '#f00' }}>{err}</span> : '-'
              }
            ]}
          />
        </div>
      )
    }

    const prediction = result.prediction || result
    const isRegression = prediction.predicted_return !== undefined

    return (
      <div style={{ marginTop: 16, padding: 12, background: '#1a1a2e', borderRadius: 4 }}>
        <div style={{ color: '#888', marginBottom: 8 }}>
          预测结果 - {result.stock_name || result.stock_code || ''}
          {prediction.label_type === 'multi' && <Tag color="purple" size="small">5分类</Tag>}
        </div>

        {isRegression ? (
          <>
            <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 8 }}>
              <Tag color={getSignalColor(prediction.signal)} style={{ fontSize: 16, padding: '4px 16px' }}>
                {prediction.signal}
              </Tag>
              <span style={{ color: '#fff' }}>
                预测收益率: {(prediction.predicted_return * 100).toFixed(2)}%
              </span>
              {prediction.confidence !== null && prediction.confidence !== undefined && (
                <span style={{ color: '#fff' }}>
                  置信度: {(prediction.confidence * 100).toFixed(1)}%
                </span>
              )}
            </div>
            {prediction.model_predictions && (
              <div style={{ fontSize: 12, color: '#888' }}>
                <div style={{ marginBottom: 4 }}>各模型预测:</div>
                {Object.entries(prediction.model_predictions).map(([name, pred]) => (
                  <span key={name} style={{ marginRight: 12 }}>
                    {name}: {(pred * 100).toFixed(2)}%
                  </span>
                ))}
                {prediction.std !== undefined && (
                  <div style={{ marginTop: 4 }}>标准差: {(prediction.std * 100).toFixed(2)}%</div>
                )}
              </div>
            )}
          </>
        ) : (
          <>
            <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
              <Tag color={getSignalColor(prediction.signal)} style={{ fontSize: 16, padding: '4px 16px' }}>
                {prediction.signal}
              </Tag>
              {prediction.confidence != null && !Number.isNaN(prediction.confidence) && (
                <span style={{ color: '#fff' }}>置信度: {(prediction.confidence * 100).toFixed(1)}%</span>
              )}
            </div>
            <div style={{ marginTop: 8, fontSize: 12, color: '#888' }}>
              {Object.entries(prediction.probabilities || {}).map(([key, val]) => (
                <span key={key} style={{ marginRight: 12 }}>
                  {key}: {(val * 100).toFixed(1)}%
                </span>
              ))}
            </div>
          </>
        )}
      </div>
    )
  }

  const currentFeatures = getCurrentFeatures()

  // 渲染任务队列
  const renderTaskQueue = () => (
    <Card
      size="small"
      title={
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span>任务队列 ({taskQueue.length})</span>
          {taskQueue.length > 0 && (
            <Button size="small" icon={<ClearOutlined />} onClick={clearTaskQueue}>
              清空
            </Button>
          )}
        </div>
      }
      style={{ height: 250, overflow: 'auto' }}
    >
      {taskQueue.length === 0 ? (
        <div style={{ textAlign: 'center', color: '#888', padding: '20px 0' }}>
          暂无任务，请在左侧添加
        </div>
      ) : (
        <List
          size="small"
          dataSource={taskQueue}
          renderItem={(task, index) => (
            <List.Item
              style={{ padding: '4px 0' }}
              actions={[
                <Button
                  size="small"
                  type="text"
                  danger
                  icon={<DeleteOutlined />}
                  onClick={() => removeTaskFromQueue(task.id)}
                />
              ]}
            >
              <div style={{ fontSize: 12 }}>
                <div><strong>任务 {index + 1}:</strong> {task.stockDisplay}</div>
                <div style={{ color: '#888' }}>
                  {task.model_type} | {task.horizon}天 | 阈值{task.threshold * 100}% | {task.mode === 'regression' ? '回归' : '分类'}
                </div>
              </div>
            </List.Item>
          )}
        />
      )}
      {taskQueue.length > 0 && (
        <Button
          type="primary"
          icon={<PlayCircleOutlined />}
          onClick={submitTaskQueue}
          loading={training}
          style={{ width: '100%', marginTop: 8 }}
        >
          开始训练 ({taskQueue.length}个任务)
        </Button>
      )}
    </Card>
  )

  // 渲染训练状态
  const renderTrainingStatus = () => (
    <Card size="small" title="训练状态" style={{ marginTop: 8 }}>
      {training && currentTaskIndex >= 0 && totalTasks > 0 && (
        <div style={{ marginBottom: 8, fontSize: 12, color: '#1890ff' }}>
          <strong>当前: 任务 {currentTaskIndex + 1}/{totalTasks}</strong>
        </div>
      )}
      {training && trainingLogs.length > 0 && (
        <div style={{ marginBottom: 8, fontSize: 12, color: '#888' }}>
          {trainingLogs[0].status} - {trainingLogs[0].message || '处理中...'}
        </div>
      )}
      {training && <Progress percent={progress} size="small" status="active" />}
      {!training && trainingLogs.length > 0 && (
        <div style={{ fontSize: 12, color: '#888' }}>
          上次训练: {trainingLogs[0].status}
        </div>
      )}
      {training && (
        <Button
          type="primary"
          danger
          icon={<StopOutlined />}
          onClick={handleStopTraining}
          style={{ width: '100%', marginTop: 8 }}
        >
          停止训练
        </Button>
      )}
    </Card>
  )

  return (
    <Card
      size="small"
      title={<><RobotOutlined /> 机器学习</>}
      style={{ height: '100%', overflow: 'auto' }}
    >
      <Tabs defaultActiveKey="1" size="small">
        <Tabs.TabPane tab="训练" key="1">
          <div style={{ display: 'flex', gap: 16 }}>
            {/* 左侧：参数设置 */}
            <div style={{ flex: 1 }}>
              <Form form={form} layout="vertical">
                <Space direction="vertical" style={{ width: '100%' }}>
                  <div style={{ display: 'flex', gap: 8 }}>
                    <Form.Item name="market" label="市场" style={{ marginBottom: 0 }}>
                      <Select value={selectedMarket} onChange={handleMarketChange} style={{ width: 80 }}>
                        {markets.map(m => <Select.Option key={m} value={m}>{m}</Select.Option>)}
                      </Select>
                    </Form.Item>
                    <Form.Item name="period" label="周期" style={{ marginBottom: 0 }}>
                      <Select value={selectedPeriod} onChange={handlePeriodChange} style={{ width: 80 }}>
                        {periods.map(p => <Select.Option key={p} value={p}>{p}</Select.Option>)}
                      </Select>
                    </Form.Item>
                    <Form.Item name="stock" label="股票" rules={[{ required: true }]} style={{ flex: 1, marginBottom: 0 }}>
                      <Select
                        mode="multiple"
                        showSearch
                        allowClear
                        placeholder="选择股票（支持多选）"
                        maxTagCount={3}
                      >
                        <Select.Option key="select_all" value="__SELECT_ALL__">全选</Select.Option>
                        {(stocks || []).map(s => (
                          <Select.Option key={s} value={s}>{s}</Select.Option>
                        ))}
                      </Select>
                    </Form.Item>
                  </div>

                  <Form.Item name="modelName" label="模型名称" style={{ marginBottom: 8 }}>
                    <Input.Group compact style={{ display: 'flex' }}>
                      <Input style={{ flex: 1 }} placeholder="自动生成" />
                      <Button onClick={() => form.setFieldsValue({ modelName: generateModelName() })}>刷新</Button>
                    </Input.Group>
                  </Form.Item>

                  <Form.Item name="useEnsemble" label="使用集成模型" valuePropName="checked" style={{ marginBottom: 8 }}>
                    <Switch />
                  </Form.Item>

                  <Form.Item name="modelType" label="基础模型" style={{ marginBottom: 8 }}>
                    <Select disabled={useEnsemble}>
                      <Select.Option value="RandomForest">RandomForest</Select.Option>
                      <Select.Option value="LightGBM">LightGBM</Select.Option>
                    </Select>
                  </Form.Item>

                  <Form.Item name="trainMode" label="训练方式" style={{ marginBottom: 8 }} initialValue="thread">
                    <Select>
                      <Select.Option value="thread">多线程</Select.Option>
                      <Select.Option value="process">多进程</Select.Option>
                    </Select>
                  </Form.Item>

                  <Form.Item name="endDate" label="结束日期" style={{ marginBottom: 0 }}>
                    <DatePicker placeholder="结束日期" format="YYYYMMDD" />
                  </Form.Item>

                  <div style={{ display: 'flex', gap: 8 }}>
                    <Form.Item name="mode" label="训练模式" style={{ flex: 1, marginBottom: 0 }} initialValue="classification">
                      <Select placeholder="默认分类">
                        <Select.Option value="classification">分类</Select.Option>
                        <Select.Option value="regression">回归</Select.Option>
                      </Select>
                    </Form.Item>
                    <Form.Item name="horizon" label="预测天数" style={{ flex: 1, marginBottom: 0 }}>
                      <Input type="number" placeholder="默认5" min={1} max={60} />
                    </Form.Item>
                  </div>

                  <Form.Item name="labelType" label="分类标签" style={{ marginBottom: 8 }} initialValue="fixed">
                    <Select placeholder="默认固定阈值">
                      <Select.Option value="fixed">固定阈值</Select.Option>
                      <Select.Option value="volatility">波动率动态</Select.Option>
                      <Select.Option value="multi">多分类</Select.Option>
                    </Select>
                  </Form.Item>

                  <div style={{ display: 'flex', gap: 8 }}>
                    <Form.Item name="threshold" label="阈值%" style={{ flex: 1, marginBottom: 0 }}>
                      <Input type="number" placeholder="默认2" min={0.1} max={10} step={0.1} />
                    </Form.Item>
                    <Form.Item name="volWindow" label="波动窗口" style={{ flex: 1, marginBottom: 0 }}>
                      <Input type="number" placeholder="默认20" min={5} max={60} />
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
                          setSelectedFeatures(alphaFeatures)
                          form.setFieldsValue({ features: alphaFeatures })
                        } else if (featureType === 'technical') {
                          setSelectedFeatures(technicalFeatures)
                          form.setFieldsValue({ features: technicalFeatures })
                        } else {
                          setSelectedFeatures([...technicalFeatures, ...alphaFeatures])
                          form.setFieldsValue({ features: [...technicalFeatures, ...alphaFeatures] })
                        }
                      }}
                    >
                      全选
                    </Button>
                    <Button type="link" size="small" onClick={() => { setSelectedFeatures([]); form.setFieldsValue({ features: [] }) }}>
                      清空
                    </Button>
                  </div>

                  <Button
                    type="dashed"
                    icon={<PlusOutlined />}
                    onClick={addTaskToQueue}
                    style={{ width: '100%' }}
                  >
                    添加任务
                  </Button>
                </Space>
              </Form>
            </div>

            {/* 右侧：任务队列和训练状态 */}
            <div style={{ width: 300 }}>
              {renderTaskQueue()}
              {renderTrainingStatus()}
            </div>
          </div>
        </Tabs.TabPane>

        <Tabs.TabPane tab="增量训练" key="2">
          <Form layout="vertical" onFinish={handleIncrementalTrain}>
            <Space direction="vertical" style={{ width: '100%' }}>
              <Form.Item name="base_model" label="基座模型" rules={[{ required: true }]} style={{ marginBottom: 8 }}>
                <Select placeholder="选择基座模型">
                  {Array.isArray(models) && models.filter(m => !m.is_ensemble).map(m => (
                    <Select.Option key={m.id} value={m.id}>
                      {m.model_name || m.stock} [{m.model_type || ''}]
                    </Select.Option>
                  ))}
                </Select>
              </Form.Item>

              <Form.Item name="stock" label="股票" rules={[{ required: true }]} style={{ marginBottom: 0 }}>
                <Select showSearch allowClear placeholder="选择股票">
                  {(stocks || []).map(s => (
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
              <Form.Item name="model_id" label="选择模型" rules={[{ required: true }]} style={{ marginBottom: 8 }}>
                <Select placeholder="选择模型">
                  {Array.isArray(models) && models.map(m => (
                    <Select.Option key={m.id || m.model_name} value={m.id || m.model_name}>
                      {m.model_name || m.id} [{m.model_type || ''}]
                    </Select.Option>
                  ))}
                </Select>
              </Form.Item>

              <Form.Item name="stock" label="股票代码" rules={[{ required: true }]} style={{ marginBottom: 8 }}>
                <Input placeholder="输入股票代码，多个用逗号分隔" />
              </Form.Item>

              <Form.Item name="period" label="周期" initialValue="1d" style={{ marginBottom: 8 }}>
                <Select>
                  <Select.Option value="1d">日线</Select.Option>
                  <Select.Option value="1w">周线</Select.Option>
                  <Select.Option value="1m">月线</Select.Option>
                </Select>
              </Form.Item>

              <Button type="primary" htmlType="submit" icon={<RobotOutlined />} loading={loading} style={{ width: '100%' }}>
                预测
              </Button>

              {renderPredictionResult(predictionResult)}
            </Space>
          </Form>
        </Tabs.TabPane>

        <Tabs.TabPane tab="训练记录" key="4">
          <Table
            size="small"
            dataSource={Array.isArray(trainingLogs) ? trainingLogs : []}
            rowKey="id"
            pagination={false}
            scroll={{ y: 200 }}
            columns={[
              { title: '时间', dataIndex: 'time', width: 120 },
              { title: '股票', dataIndex: 'stock', width: 80 },
              { title: '模型', dataIndex: 'model', width: 100 },
              { title: '特征', dataIndex: 'features', width: 50 },
              {
                title: '进度',
                dataIndex: 'progress',
                width: 80,
                render: (pct, record) => record.status.includes('完成') || record.status.includes('失败')
                  ? null
                  : <Progress percent={pct || 0} size="small" status="active" />
              },
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
              {
                title: '信息',
                dataIndex: 'message',
                width: 150,
                ellipsis: true
              }
            ]}
          />
        </Tabs.TabPane>

        <Tabs.TabPane tab="已训练模型" key="5">
          <div style={{ maxHeight: 400, overflow: 'auto' }}>
            {Object.keys(ensembleGroups).map(parentId => (
              <Card size="small" key={parentId} title={<Tag color="purple">集成 #{parentId}</Tag>} style={{ marginBottom: 8 }}>
                <Table
                  size="small"
                  dataSource={ensembleGroups[parentId] || []}
                  rowKey="id"
                  pagination={false}
                  columns={[
                    { title: '模型', dataIndex: 'model_name', ellipsis: true },
                    { title: '类型', dataIndex: 'model_type', width: 120 },
                    { title: '股票', dataIndex: 'stock_code', width: 80 },
                    { title: '特征', dataIndex: 'feature_count', width: 50 },
                    { title: '训练时间', dataIndex: 'created_at', width: 120, render: v => v?.slice(0, 19) },
                    {
                      title: '操作',
                      width: 60,
                      render: (_, record) => (
                        <Button size="small" type="text" danger icon={<DeleteOutlined />} onClick={() => handleDeleteModel(record.id)} />
                      )
                    }
                  ]}
                />
              </Card>
            ))}
            <Table
              size="small"
              title={() => '单模型'}
              dataSource={Array.isArray(models) ? models : []}
              rowKey="id"
              pagination={false}
              columns={[
                { title: '模型名称', dataIndex: 'model_name', ellipsis: true },
                { title: '类型', dataIndex: 'model_type', width: 120 },
                { title: '股票', dataIndex: 'stock_code', width: 80 },
                { title: '特征', dataIndex: 'feature_count', width: 50 },
                { title: '训练时间', dataIndex: 'created_at', width: 120, render: v => v?.slice(0, 19) },
                {
                  title: '操作',
                  width: 60,
                  render: (_, record) => (
                    <Button size="small" type="text" danger icon={<DeleteOutlined />} onClick={() => handleDeleteModel(record.id)} />
                  )
                }
              ]}
            />
          </div>
        </Tabs.TabPane>
      </Tabs>
    </Card>
  )
}

export default MLPanel
