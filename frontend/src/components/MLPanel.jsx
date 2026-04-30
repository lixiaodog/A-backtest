import React, { useState, useEffect, useCallback } from 'react'
import { Form, DatePicker, Select, Button, Card, Checkbox, Progress, Table, Tag, Tabs, Space, message, Input, Switch, List, Divider, Modal, Descriptions, Alert, Statistic, Row, Col, Tooltip, TreeSelect, Slider } from 'antd'
import { RobotOutlined, DeleteOutlined, PlayCircleOutlined, CloudUploadOutlined, StopOutlined, PlusOutlined, ClearOutlined, DownloadOutlined, ReloadOutlined, SyncOutlined, CheckCircleOutlined, CloseCircleOutlined, PauseCircleOutlined, SettingOutlined } from '@ant-design/icons'
import axios from 'axios'
import dayjs from 'dayjs'

const { Option } = Select
const { TextArea } = Input

function MLPanel() {
  const [markets, setMarkets] = useState(['SZ', 'SH', 'BJ'])
  const [periods, setPeriods] = useState(['1d', '1m', '5m', '15m', '30m', '60m', '1h', '4h', '1w'])
  const [selectedMarket, setSelectedMarket] = useState('SZ')
  const [selectedPeriod, setSelectedPeriod] = useState('1d')
  const [stocks, setStocks] = useState([])
  const [loading, setLoading] = useState(false)
  const [models, setModels] = useState([])
  const [ensembleGroups, setEnsembleGroups] = useState({})
  const [technicalFeatures, setTechnicalFeatures] = useState([])
  const [alphaFeatures, setAlphaFeatures] = useState([])
  const [selectedFeatures, setSelectedFeatures] = useState([])
  const [featureType, setFeatureType] = useState('all')
  const [predictionResult, setPredictionResult] = useState(null)

  // 新增状态 - 任务管理
  const [trainingTasks, setTrainingTasks] = useState([])
  const [pendingQueue, setPendingQueue] = useState([])
  const [configVisible, setConfigVisible] = useState(false)
  const [detailVisible, setDetailVisible] = useState(false)
  const [selectedTask, setSelectedTask] = useState(null)
  const [refreshInterval, setRefreshInterval] = useState(null)

  // 选股状态
  const [advancedPredictLoading, setAdvancedPredictLoading] = useState(false)
  const [advancedPredictTaskId, setAdvancedPredictTaskId] = useState(null)
  const [advancedPredictProgress, setAdvancedPredictProgress] = useState(0)
  const [advancedPredictResults, setAdvancedPredictResults] = useState(null)
  const [advancedPredictStatus, setAdvancedPredictStatus] = useState('')
  const [advancedPredictTasks, setAdvancedPredictTasks] = useState([])
  const [activeTab, setActiveTab] = useState('1')

  // 评估状态
  const [evaluateSectors, setEvaluateSectors] = useState([])
  const [evaluateTaskId, setEvaluateTaskId] = useState(null)
  const [evaluateProgress, setEvaluateProgress] = useState(0)
  const [evaluateResults, setEvaluateResults] = useState(null)
  const [evaluateTasks, setEvaluateTasks] = useState([])
  const [evaluateModelId, setEvaluateModelId] = useState(null)
  const [evaluateHorizon, setEvaluateHorizon] = useState(null)
  const [evaluateLoading, setEvaluateLoading] = useState(false)

  const [form] = Form.useForm()
  const useEnsemble = Form.useWatch('useEnsemble', form)
  const watchMode = Form.useWatch('mode', form)
  const watchLabelType = Form.useWatch('labelType', form)

  const fetchTrainingTasks = useCallback(async () => {
    try {
      const response = await axios.get('http://localhost:5000/api/ml/train/tasks')
      console.log(response.data.tasks)
      setTrainingTasks(response.data.tasks || [])
    } catch (error) {
      console.error('获取任务列表失败:', error)
    }
  }, [])

  const startAutoRefresh = useCallback(() => {
    if (refreshInterval) return
    fetchTrainingTasks()
    const interval = setInterval(() => {
      fetchTrainingTasks()
    }, 10000)
    setRefreshInterval(interval)
  }, [refreshInterval, fetchTrainingTasks])

  const stopAutoRefresh = useCallback(() => {
    if (refreshInterval) {
      clearInterval(refreshInterval)
      setRefreshInterval(null)
    }
  }, [refreshInterval])

  useEffect(() => {
    loadModels()
    loadTechnicalFeatures()
    loadAlphaFeatures()
    loadMarkets()
    loadPeriods()
    loadStocks()
    fetchTrainingTasks()
  }, [fetchTrainingTasks])

  useEffect(() => {
    startAutoRefresh()
    return () => stopAutoRefresh()
  }, [startAutoRefresh, stopAutoRefresh])

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
      const allModels = data.models || []
      
      const groups = {}
      const singles = []
      
      allModels.forEach(m => {
        if (m.is_ensemble && m.sub_models && m.sub_models.length > 0) {
          groups[m.id] = [{
            id: m.id,
            model_name: m.model_name,
            model_type: m.model_type,
            stock_code: m.stock_code,
            created_at: m.created_at,
            sub_models: m.sub_models
          }]
        } else {
          singles.push(m)
        }
      })
      
      setModels(singles)
      setEnsembleGroups(groups)
    } catch (err) {
      console.error('Failed to load models:', err)
    }
  }

  const handleTabChange = (key) => {
    setActiveTab(key)
    if (key === '3') {
      loadModels()
    } else if (key === '5') {
      loadModels()
    } else if (key === 'advanced') {
      loadModels()
      fetchAdvancedPredictTasks()
    } else if (key === 'evaluate') {
      loadModels()
      loadEvaluateSectors()
      fetchEvaluateTasks()
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

  // 添加任务到待提交队列
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

    const horizon = values.horizon ? parseInt(values.horizon) : 5
    const threshold = values.threshold ? parseFloat(values.threshold) : 2
    const volWindow = values.volWindow ? parseInt(values.volWindow) : 20
    const modelType = values.modelType || 'RandomForest'
    const trainMode = values.mode || 'classification'
    const useEnsemble = values.useEnsemble || false

    const market = selectedMarket || 'SZ'
    const period = (selectedPeriod || '1d').toUpperCase()
    const newTask = {
      id: `pending_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      stock: selectedStocks,
      stockDisplay: stockDisplay,
      market: selectedMarket,
      period: selectedPeriod,
      end_date: values.endDate ? dayjs(values.endDate).format('YYYYMMDD') : '',
      features: [...selectedFeatures],
      model_type: values.modelType || 'RandomForest',
      horizon: horizon,
      threshold: threshold / 100,
      label_type: values.labelType || 'fixed',
      vol_window: volWindow,
      lower_q: 0.2,
      upper_q: 0.8,
      mode: values.mode || 'classification',
      use_ensemble: values.useEnsemble || false,
      test_size: 0.2,
      train_mode: values.trainMode || 'thread',
      data_source: values.dataSource || 'cache',
      fast_mode: values.fastMode || false,
      use_gpu: values.useGpu || false,
      normalize: values.normalize || false
    }

    setPendingQueue(prev => [...prev, newTask])
    message.success(`已添加任务: ${stockDisplay}`)
    setConfigVisible(false)
  }

  // 从队列移除任务
  const removeTaskFromQueue = (taskId) => {
    setPendingQueue(prev => prev.filter(t => t.id !== taskId))
  }

  // 清空任务队列
  const clearTaskQueue = () => {
    setPendingQueue([])
    message.info('任务队列已清空')
  }

  // 提交任务队列进行训练
  const submitTaskQueue = async () => {
    if (pendingQueue.length === 0) {
      message.error('任务队列为空，请先添加任务')
      return
    }

    setLoading(true)

    try {
      const tasksToSubmit = pendingQueue.map(task => {
        const { id, stockDisplay, ...taskData } = task
        return taskData
      })

      const res = await axios.post('http://localhost:5000/api/ml/train/batch', {
        tasks: tasksToSubmit
      })

      message.success(`训练任务已启动: ${res.data.task_id} (${pendingQueue.length}个任务)`)
      setPendingQueue([])
      fetchTrainingTasks()
    } catch (err) {
      message.error('训练失败: ' + (err.response?.data?.error || err.message || '未知错误'))
    } finally {
      setLoading(false)
    }
  }

  // 停止任务
  const handleStopTask = async (taskId) => {
    try {
      await axios.post(`http://localhost:5000/api/ml/train/stop/${taskId}`)
      message.success('任务已停止')
      fetchTrainingTasks()
    } catch (error) {
      message.error('停止任务失败: ' + (error.response?.data?.error || error.message))
    }
  }

  // 删除任务
  const handleDeleteTask = async (taskId) => {
    try {
      await axios.delete(`http://localhost:5000/api/ml/train/tasks/${taskId}`)
      message.success('任务已删除')
      fetchTrainingTasks()
    } catch (error) {
      message.error('删除任务失败: ' + (error.response?.data?.error || error.message))
    }
  }

  // 查看任务详情
  const handleViewDetail = (task) => {
    setSelectedTask(task)
    setDetailVisible(true)
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

    setLoading(true)

    try {
      const res = await axios.post('http://localhost:5000/api/ml/train/incremental', {
        stock: values.stock,
        end_date: values.endDate ? dayjs(values.endDate).format('YYYYMMDD') : '',
        features: selectedFeatures,
        model_id: modelId
      })

      message.success('增量训练完成!')
      loadModels()
    } catch (err) {
      message.error('增量训练失败')
    } finally {
      setLoading(false)
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

      const predictDate = values.predict_date ? dayjs(values.predict_date).format('YYYYMMDD') : null

      const res = await axios.post('http://localhost:5000/api/ml/predict', {
        stocks: stocks,
        model_id: values.model_id,
        period: values.period || '1d',
        data_source: values.data_source || 'akshare',
        predict_date: predictDate
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

  // 选股处理函数
  const handleAdvancedPredict = async (values) => {
    if (!values.model_ids || values.model_ids.length === 0) {
      message.error('请至少选择一个模型')
      return
    }

    setAdvancedPredictLoading(true)
    setAdvancedPredictProgress(0)
    setAdvancedPredictResults(null)
    setAdvancedPredictStatus('准备预测...')

    try {
      const stockCodes = values.stocks ? values.stocks.split(',').map(s => s.trim()).filter(s => s) : []

      const requestData = {
        data_source: values.data_source || 'akshare',
        markets: values.markets || [],
        stocks: stockCodes,
        model_ids: values.model_ids,
        sort_by: values.sort_by || 'confidence',
        sort_order: values.sort_order || 'desc',
        top_n: values.top_n || 100,
        fusion_mode: values.fusion_mode || 'intersection',
        period: values.period || '1d',
        predict_date: values.predict_date ? dayjs(values.predict_date).format('YYYY-MM-DD') : ''
      }

      const res = await axios.post('http://localhost:5000/api/ml/predict/advanced', requestData)

      const taskId = res.data.task_id
      setAdvancedPredictTaskId(taskId)
      setAdvancedPredictStatus('预测进行中...')

      const pollProgress = setInterval(async () => {
        try {
          const progressRes = await axios.get(`http://localhost:5000/api/ml/predict/advanced/${taskId}`)
          const data = progressRes.data

          setAdvancedPredictProgress(data.progress || 0)
          setAdvancedPredictStatus(data.message || '处理中...')

          if (data.status === 'completed') {
            clearInterval(pollProgress)
            setAdvancedPredictResults(data)
            setAdvancedPredictStatus('预测完成')
            message.success(`预测完成，共筛选出 ${data.fused_results?.length || 0} 只股票`)
            setAdvancedPredictLoading(false)
          } else if (data.status === 'failed') {
            clearInterval(pollProgress)
            setAdvancedPredictStatus('预测失败')
            message.error('预测失败: ' + data.message)
            setAdvancedPredictLoading(false)
          }
        } catch (e) {
          clearInterval(pollProgress)
          setAdvancedPredictStatus('查询失败')
          setAdvancedPredictLoading(false)
        }
      }, 1000)
    } catch (err) {
      message.error('启动预测失败: ' + (err.response?.data?.error || err.message || '未知错误'))
      setAdvancedPredictLoading(false)
    }
  }

  // 获取选股任务列表
  const fetchAdvancedPredictTasks = useCallback(async () => {
    try {
      const response = await axios.get('http://localhost:5000/api/ml/predict/advanced/tasks')
      setAdvancedPredictTasks(response.data.tasks || [])
    } catch (error) {
      console.error('获取选股任务列表失败:', error)
    }
  }, [])

  // 停止选股任务
  const handleStopAdvancedPredict = async (taskId) => {
    try {
      await axios.post(`http://localhost:5000/api/ml/predict/advanced/${taskId}/stop`)
      message.success('正在停止任务...')
      fetchAdvancedPredictTasks()
    } catch (err) {
      message.error('停止失败: ' + (err.response?.data?.error || err.message))
    }
  }

  // 查看已完成选股任务的结果
  const handleViewAdvancedPredictResult = async (taskId) => {
    try {
      const res = await axios.get(`http://localhost:5000/api/ml/predict/advanced/${taskId}`)
      const data = res.data
      if (data.status === 'completed') {
        setAdvancedPredictResults(data)
        message.success('已加载预测结果')
      } else {
        message.info(`任务状态: ${data.status}，进度: ${data.progress}%`)
      }
    } catch (err) {
      message.error('获取结果失败: ' + (err.response?.data?.error || err.message))
    }
  }

  // 删除选股任务
  const handleDeleteAdvancedPredict = async (taskId) => {
    try {
      await axios.delete(`http://localhost:5000/api/ml/predict/advanced/${taskId}`)
      message.success('任务已删除')
      fetchAdvancedPredictTasks()
    } catch (err) {
      message.error('删除失败: ' + (err.response?.data?.error || err.message))
    }
  }

  // 定时刷新选股任务列表
  useEffect(() => {
    fetchAdvancedPredictTasks()
    const interval = setInterval(fetchAdvancedPredictTasks, 5000)
    return () => clearInterval(interval)
  }, [fetchAdvancedPredictTasks])

  const handleDeleteModel = async (modelId) => {
    try {
      await axios.delete(`http://localhost:5000/api/ml/models/${modelId}`)
      message.success('模型已删除')
      loadModels()
    } catch (err) {
      message.error('删除失败')
    }
  }

  // 加载板块树形数据
  const loadEvaluateSectors = async () => {
    try {
      const res = await axios.get('http://localhost:5000/api/ml/sectors')
      setEvaluateSectors(res.data || [])
    } catch (err) {
      console.error('加载板块数据失败:', err)
    }
  }

  // 获取评估任务列表
  const fetchEvaluateTasks = useCallback(async () => {
    try {
      const response = await axios.get('http://localhost:5000/api/ml/evaluate/tasks')
      setEvaluateTasks(response.data.tasks || [])
    } catch (error) {
      console.error('获取评估任务列表失败:', error)
    }
  }, [])

  // 提交评估任务
  const handleEvaluate = async (values) => {
    if (!values.model_id) {
      message.error('请选择模型')
      return
    }
    if (!values.sectors || values.sectors.length === 0) {
      message.error('请选择至少一个板块')
      return
    }
    if (!values.start_date || !values.end_date) {
      message.error('请选择日期范围')
      return
    }

    setEvaluateLoading(true)
    setEvaluateProgress(0)
    setEvaluateResults(null)

    try {
      const res = await axios.post('http://localhost:5000/api/ml/evaluate', {
        model_id: values.model_id,
        sectors: values.sectors,
        start_date: dayjs(values.start_date).format('YYYYMMDD'),
        end_date: dayjs(values.end_date).format('YYYYMMDD'),
        validation_ratio: (values.validation_ratio || 20) / 100
      })

      const taskId = res.data.task_id
      setEvaluateTaskId(taskId)
      message.success('评估任务已启动')

      const pollProgress = setInterval(async () => {
        try {
          const progressRes = await axios.get(`http://localhost:5000/api/ml/evaluate/${taskId}`)
          const data = progressRes.data

          setEvaluateProgress(data.progress || 0)

          if (data.status === 'completed') {
            clearInterval(pollProgress)
            setEvaluateResults(data)
            setEvaluateLoading(false)
            message.success('评估完成')
            fetchEvaluateTasks()
          } else if (data.status === 'failed') {
            clearInterval(pollProgress)
            setEvaluateLoading(false)
            message.error('评估失败: ' + data.message)
            fetchEvaluateTasks()
          }
        } catch (e) {
          clearInterval(pollProgress)
          setEvaluateLoading(false)
        }
      }, 3000)
    } catch (err) {
      message.error('启动评估失败: ' + (err.response?.data?.error || err.message || '未知错误'))
      setEvaluateLoading(false)
    }
  }

  // 查看评估结果
  const handleViewEvaluateResult = async (taskId) => {
    try {
      const res = await axios.get(`http://localhost:5000/api/ml/evaluate/${taskId}`)
      const data = res.data
      if (data.status === 'completed') {
        setEvaluateResults(data)
        message.success('已加载评估结果')
      } else {
        message.info(`任务状态: ${data.status}，进度: ${data.progress}%`)
      }
    } catch (err) {
      message.error('获取结果失败: ' + (err.response?.data?.error || err.message))
    }
  }

  // 模型选择变化时自动填充预测天数
  const handleEvaluateModelChange = (modelId) => {
    setEvaluateModelId(modelId)
    let horizon = null
    for (const m of (Array.isArray(models) ? models : [])) {
      if (m.id === modelId || m.model_name === modelId) {
        horizon = m.horizon
        break
      }
    }
    if (!horizon) {
      for (const [, group] of Object.entries(ensembleGroups)) {
        for (const m of group) {
          if (m.id === modelId) {
            horizon = m.horizon
            break
          }
        }
        if (horizon) break
      }
    }
    setEvaluateHorizon(horizon)
  }

  // 渲染评估指标
  const renderEvaluateMetrics = (metrics, title) => {
    if (!metrics || metrics.error) {
      return <Alert type="warning" message={metrics?.error || metrics?.message || '无数据'} style={{ marginBottom: 8 }} />
    }
    if (metrics.message) {
      return <Alert type="info" message={metrics.message} style={{ marginBottom: 8 }} />
    }

    const isRegression = metrics.mse !== undefined

    if (isRegression) {
      return (
        <Card size="small" title={title} style={{ marginBottom: 8 }}>
          <Row gutter={16}>
            <Col span={8}><Statistic title="MSE" value={metrics.mse} precision={6} /></Col>
            <Col span={8}><Statistic title="RMSE" value={metrics.rmse} precision={6} /></Col>
            <Col span={8}><Statistic title="MAE" value={metrics.mae} precision={6} /></Col>
          </Row>
          <Row gutter={16} style={{ marginTop: 8 }}>
            <Col span={8}><Statistic title="R²" value={metrics.r2} precision={4} /></Col>
            <Col span={8}><Statistic title="方向准确率" value={(metrics.direction_accuracy * 100).toFixed(2)} suffix="%" /></Col>
            <Col span={8}><Statistic title="样本数" value={metrics.total_samples} /></Col>
          </Row>
        </Card>
      )
    }

    return (
      <Card size="small" title={title} style={{ marginBottom: 8 }}>
        <Row gutter={16}>
          <Col span={6}><Statistic title="准确率" value={(metrics.accuracy * 100).toFixed(2)} suffix="%" /></Col>
          <Col span={6}><Statistic title="精确率" value={(metrics.precision * 100).toFixed(2)} suffix="%" /></Col>
          <Col span={6}><Statistic title="召回率" value={(metrics.recall * 100).toFixed(2)} suffix="%" /></Col>
          <Col span={6}><Statistic title="F1" value={(metrics.f1 * 100).toFixed(2)} suffix="%" /></Col>
        </Row>
        <Row gutter={16} style={{ marginTop: 8 }}>
          <Col span={12}><Statistic title="样本数" value={metrics.total_samples} /></Col>
        </Row>
        {metrics.per_class && (
          <Table
            size="small"
            style={{ marginTop: 8 }}
            dataSource={Object.entries(metrics.per_class).map(([name, data]) => ({ key: name, name, ...data }))}
            pagination={false}
            columns={[
              { title: '类别', dataIndex: 'name', width: 100 },
              { title: '精确率', dataIndex: 'precision', render: v => `${(v * 100).toFixed(2)}%` },
              { title: '召回率', dataIndex: 'recall', render: v => `${(v * 100).toFixed(2)}%` },
              { title: 'F1', dataIndex: 'f1', render: v => `${(v * 100).toFixed(2)}%` },
              { title: '样本数', dataIndex: 'support', width: 80 }
            ]}
          />
        )}
      </Card>
    )
  }

  // 定时刷新评估任务列表
  useEffect(() => {
    fetchEvaluateTasks()
    const interval = setInterval(fetchEvaluateTasks, 5000)
    return () => clearInterval(interval)
  }, [fetchEvaluateTasks])

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

  // 渲染选股结果
  const renderAdvancedPredictionResult = () => {
    if (!advancedPredictResults) return null

    const { fused_results, results, total_stocks, processed_stocks, export_files } = advancedPredictResults

    const renderDownloadLinks = () => {
      if (!export_files || Object.keys(export_files).length === 0) return null
      
      const task_id = advancedPredictResults?.task_id
      
      return (
        <div style={{ marginBottom: 16 }}>
          <div style={{ fontWeight: 'bold', marginBottom: 8 }}>导出文件:</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center' }}>
            <Button 
              size="small" 
              type="primary"
              icon={<DownloadOutlined />}
              style={{ backgroundColor: '#52c41a', borderColor: '#52c41a' }}
              onClick={() => window.open(`http://localhost:5000/api/ml/predict/advanced/${task_id}/download_all`, '_blank')}
            >
              一键下载全部
            </Button>
            <Divider type="vertical" style={{ backgroundColor: '#444', height: 20 }} />
            {Object.entries(export_files).map(([key, file]) => (
              <Button 
                key={key}
                size="small" 
                icon={<DownloadOutlined />}
                onClick={() => window.open(`http://localhost:5000${file.url}`, '_blank')}
              >
                {key === 'fused' ? '融合结果' : `模型 ${key.slice(0, 8)}...`}
              </Button>
            ))}
          </div>
        </div>
      )
    }

    return (
      <div style={{ marginTop: 16 }}>
        {renderDownloadLinks()}
        
        <Card size="small" title="融合结果" style={{ marginBottom: 8 }}>
          <div style={{ marginBottom: 8, color: '#888' }}>
            共处理 {processed_stocks}/{total_stocks} 只股票，筛选出 {fused_results?.length || 0} 只
          </div>
          <Table
            size="small"
            dataSource={fused_results || []}
            rowKey="stock_code"
            pagination={{ pageSize: 10, size: 'small' }}
            scroll={{ y: 750 }}
            columns={(() => {
              const first = (fused_results || [])[0] || {}
              const isRegression = first.mode === 'regression'
              const base = [
                { title: '排名', dataIndex: 'rank', width: 60 },
                { title: '股票', dataIndex: 'stock_code', width: 80 },
                { title: '名称', dataIndex: 'stock_name', width: 100 }
              ]
              if (isRegression) {
                return [...base,
                  {
                    title: '预期收益率',
                    dataIndex: 'predicted_return',
                    width: 100,
                    render: v => v ? `${(v * 100).toFixed(2)}%` : '-'
                  }
                ]
              }
              return [...base,
                {
                  title: '买入概率',
                  dataIndex: 'buy_probability',
                  width: 80,
                  render: v => v ? `${(v * 100).toFixed(1)}%` : '-'
                },
                {
                  title: '持有概率',
                  dataIndex: 'hold_probability',
                  width: 80,
                  render: v => v ? `${(v * 100).toFixed(1)}%` : '-'
                },
                {
                  title: '卖出概率',
                  dataIndex: 'sell_probability',
                  width: 80,
                  render: v => v ? `${(v * 100).toFixed(1)}%` : '-'
                }
              ]
            })()}
          />
        </Card>

        {results && Object.keys(results).length > 0 && (
          <Card size="small" title="各模型结果">
            {Object.entries(results).map(([modelId, modelResults]) => {
              const first = (modelResults || [])[0] || {}
              const isRegression = first.mode === 'regression'
              const baseCols = [
                { title: '排名', dataIndex: 'rank', width: 60 },
                { title: '股票', dataIndex: 'stock_code', width: 80 },
                { title: '名称', dataIndex: 'stock_name', width: 100 }
              ]
              let modelCols
              if (isRegression) {
                modelCols = [...baseCols,
                  {
                    title: '预期收益率',
                    dataIndex: 'predicted_return',
                    width: 100,
                    render: v => v ? `${(v * 100).toFixed(2)}%` : '-'
                  }
                ]
              } else {
                modelCols = [...baseCols,
                  {
                    title: '买入概率',
                    dataIndex: 'buy_probability',
                    width: 80,
                    render: v => v ? `${(v * 100).toFixed(1)}%` : '-'
                  },
                  {
                    title: '持有概率',
                    dataIndex: 'hold_probability',
                    width: 80,
                    render: v => v ? `${(v * 100).toFixed(1)}%` : '-'
                  },
                  {
                    title: '卖出概率',
                    dataIndex: 'sell_probability',
                    width: 80,
                    render: v => v ? `${(v * 100).toFixed(1)}%` : '-'
                  }
                ]
              }
              return (
                <div key={modelId} style={{ marginBottom: 12 }}>
                  <div style={{ fontWeight: 'bold', marginBottom: 4 }}>{modelResults[0]?.model_name || modelId}</div>
                  <Table
                    size="small"
                    dataSource={modelResults.slice(0, 5)}
                    rowKey="stock_code"
                    pagination={false}
                    columns={modelCols}
                  />
                </div>
              )
            })}
          </Card>
        )}
      </div>
    )
  }

  const currentFeatures = getCurrentFeatures()

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
      width: 80,
      render: (type) => (
        <Tag color={type === 'batch' ? 'blue' : 'green'} size="small">
          {type === 'batch' ? '批量' : '单任务'}
        </Tag>
      )
    },
    {
      title: '模式',
      dataIndex: 'train_mode',
      key: 'train_mode',
      width: 80,
      render: (train_mode) => {
        const modeMap = {
          'single': { text: '单线程', color: 'default' },
          'process': { text: '多进程', color: 'blue' },
          'thread': { text: '多线程', color: 'cyan' }
        }
        const config = modeMap[train_mode] || modeMap.thread
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
      width: 150,
      render: (progress, record) => (
        <Progress 
          percent={Math.round(progress)} 
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
      title: '模型',
      key: 'model_type',
      width: 100,
      render: (_, record) => {
        const params = record.params || {}
        if (params.use_ensemble) {
          return <Tag size="small" color="purple">ENS</Tag>
        }
        const modelType = params.model_type || 'RandomForest'
        const modelMap = {
          'RandomForest': { text: 'RF', color: 'blue' },
          'LightGBM': { text: 'LGB', color: 'green' },
          'Ridge': { text: 'Ridge', color: 'orange' }
        }
        const config = modelMap[modelType] || { text: modelType.substring(0, 3).toUpperCase(), color: 'default' }
        return <Tag size="small" color={config.color}>{config.text}</Tag>
      }
    },
    {
      title: '开始时间',
      dataIndex: 'start_time',
      key: 'start_time',
      width: 160,
      render: (time) => time ? new Date(time * 1000).toLocaleString() : '-'
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
      <Tabs 
        activeKey={activeTab}
        onChange={handleTabChange}
        size="small"
        tabBarStyle={{ color: '#fff', marginBottom: 16 }}
      >
        <Tabs.TabPane tab={<span style={{ color: '#fff' }}>训练</span>} key="1">
          {/* 训练状态概览 */}
          <Card 
            title={<span><RobotOutlined /> 训练状态概览</span>}
            extra={
              <Button icon={<ReloadOutlined />} onClick={fetchTrainingTasks}>
                刷新
              </Button>
            }
            style={{ marginBottom: 16 }}
          >
            <Row gutter={16}>
              <Col span={6}>
                <Statistic 
                  title="模型数量" 
                  value={models.length + Object.keys(ensembleGroups).length} 
                  suffix="个"
                />
              </Col>
              <Col span={6}>
                <Statistic 
                  title="活跃任务" 
                  value={trainingTasks.filter(t => t.status === 'running').length} 
                  suffix="个"
                />
              </Col>
              <Col span={6}>
                <Statistic 
                  title="待提交任务" 
                  value={pendingQueue.length} 
                  suffix="个"
                  valueStyle={{ color: pendingQueue.length > 0 ? '#1890ff' : '#888' }}
                />
              </Col>
              <Col span={6}>
                <Statistic 
                  title="总特征数" 
                  value={technicalFeatures.length + alphaFeatures.length} 
                  suffix="个"
                />
              </Col>
            </Row>
          </Card>

          {/* 操作按钮 */}
          <Card style={{ marginBottom: 16 }}>
            <Space size="middle">
              <Button 
                type="primary" 
                icon={<PlusOutlined />}
                onClick={() => setConfigVisible(true)}
              >
                添加训练任务
              </Button>
              <Button 
                icon={<ClearOutlined />}
                onClick={clearTaskQueue}
                disabled={pendingQueue.length === 0}
              >
                清空队列
              </Button>
              <Button 
                type="primary"
                icon={<PlayCircleOutlined />}
                onClick={submitTaskQueue}
                loading={loading}
                disabled={pendingQueue.length === 0}
              >
                开始训练 ({pendingQueue.length}个任务)
              </Button>
            </Space>
          </Card>

          {/* 待提交任务队列 */}
          {pendingQueue.length > 0 && (
            <Card 
              size="small" 
              title={`待提交任务队列 (${pendingQueue.length})`}
              style={{ marginBottom: 16 }}
            >
              <List
                size="small"
                dataSource={pendingQueue}
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
                      <span style={{ marginRight: 8 }}>任务 {index + 1}:</span>
                      <Tag size="small">{task.market}/{task.period}</Tag>
                      <span style={{ marginRight: 8 }}>{task.stockDisplay}</span>
                      <Tag size="small" color="blue">{task.use_ensemble ? 'ENS' : task.model_type}</Tag>
                      {task.fast_mode && <Tag size="small" color="orange">快速</Tag>}
                      {task.use_gpu && <Tag size="small" color="green">GPU</Tag>}
                      <span style={{ color: '#888', marginLeft: 8 }}>
                        {task.horizon}天 | {task.threshold * 100}%阈值 | {task.features.length}特征 | {task.mode === 'regression' ? '回归' : '分类'}
                      </span>
                    </div>
                  </List.Item>
                )}
              />
            </Card>
          )}

          {/* 任务列表 */}
          <Card title="任务列表">
            <Table 
              columns={taskColumns} 
              dataSource={trainingTasks} 
              rowKey="task_id"
              pagination={{ pageSize: 10 }}
              size="small"
              locale={{ emptyText: '暂无任务' }}
              scroll={{ x: 1200 }}
            />
          </Card>

          {/* 添加任务配置弹窗 */}
          <Modal
            title="添加训练任务"
            visible={configVisible}
            onOk={addTaskToQueue}
            onCancel={() => setConfigVisible(false)}
            okText="添加到队列"
            cancelText="取消"
            width={700}
          >
            <Form form={form} layout="vertical">
              <Row gutter={16}>
                <Col span={8}>
                  <Form.Item name="market" label="市场" style={{ marginBottom: 8 }}>
                    <Select value={selectedMarket} onChange={handleMarketChange}>
                      {markets.map(m => <Option key={m} value={m}>{m}</Option>)}
                    </Select>
                  </Form.Item>
                </Col>
                <Col span={8}>
                  <Form.Item name="period" label="周期" style={{ marginBottom: 8 }}>
                    <Select value={selectedPeriod} onChange={handlePeriodChange}>
                      {periods.map(p => <Option key={p} value={p}>{p}</Option>)}
                    </Select>
                  </Form.Item>
                </Col>
                <Col span={8}>
                  <Form.Item name="dataSource" label="数据源" initialValue="cache" style={{ marginBottom: 8 }}>
                    <Select>
                      <Option value="csv">CSV文件（实时计算）</Option>
                      <Option value="cache">缓存数据</Option>
                    </Select>
                  </Form.Item>
                </Col>
              </Row>

              <Form.Item name="stock" label="股票" rules={[{ required: true }]} style={{ marginBottom: 8 }}>
                <Select
                  mode="multiple"
                  showSearch
                  allowClear
                  placeholder="选择股票（支持多选）"
                  maxTagCount={5}
                >
                  <Option key="select_all" value="__SELECT_ALL__">全选</Option>
                  {(stocks || []).map(s => (
                    <Option key={s} value={s}>{s}</Option>
                  ))}
                </Select>
              </Form.Item>

              <Row gutter={16}>
                <Col span={6}>
                  <Form.Item name="modelType" label="基础模型" style={{ marginBottom: 8 }}>
                    <Select disabled={useEnsemble}>
                      <Option value="RandomForest">RandomForest</Option>
                      <Option value="LightGBM">LightGBM</Option>
                    </Select>
                  </Form.Item>
                </Col>
                <Col span={4}>
                  <Form.Item name="useEnsemble" label="集成" valuePropName="checked" style={{ marginBottom: 8 }}>
                    <Switch />
                  </Form.Item>
                </Col>
                <Col span={4}>
                  <Form.Item name="fastMode" label="快速" valuePropName="checked" style={{ marginBottom: 8 }}>
                    <Switch />
                  </Form.Item>
                </Col>
                <Col span={4}>
                  <Form.Item name="useGpu" label="GPU" valuePropName="checked" initialValue={true} style={{ marginBottom: 8 }}>
                    <Switch defaultChecked />
                  </Form.Item>
                </Col>
              </Row>

              <Row gutter={16}>
                <Col span={8}>
                  <Form.Item name="trainMode" label="训练方式" initialValue="thread" style={{ marginBottom: 8 }}>
                    <Select>
                      <Option value="thread">多线程</Option>
                      <Option value="process">多进程</Option>
                    </Select>
                  </Form.Item>
                </Col>
                <Col span={8}>
                  <Form.Item name="endDate" label="结束日期" style={{ marginBottom: 8 }}>
                    <DatePicker placeholder="结束日期" format="YYYYMMDD" style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
                <Col span={8}>
                  <Form.Item name="normalize" label="特征归一化" initialValue={false} valuePropName="checked" style={{ marginBottom: 8 }}>
                    <Switch />
                  </Form.Item>
                </Col>
              </Row>

              <Row gutter={16}>
                <Col span={12}>
                  <Form.Item name="mode" label="训练模式" initialValue="classification" style={{ marginBottom: 8 }}>
                    <Select>
                      <Option value="classification">分类</Option>
                      <Option value="regression">回归</Option>
                    </Select>
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item name="horizon" label="预测天数" initialValue={5} style={{ marginBottom: 8 }}>
                    <Input type="number" min={1} max={60} />
                  </Form.Item>
                </Col>
              </Row>

              {watchMode !== 'regression' && (
              <Row gutter={16}>
                <Col span={8}>
                  <Form.Item name="labelType" label="分类标签" initialValue="fixed" style={{ marginBottom: 8 }}>
                    <Select>
                      <Option value="fixed">固定阈值</Option>
                      <Option value="volatility">波动率动态</Option>
                      <Option value="multi">多分类</Option>
                    </Select>
                  </Form.Item>
                </Col>
                {watchLabelType === 'fixed' && (
                <Col span={8}>
                  <Form.Item name="threshold" label="阈值%" style={{ marginBottom: 8 }}>
                    <Input type="number" placeholder="默认2" min={0.1} max={10} step={0.1} />
                  </Form.Item>
                </Col>
                )}
                {watchLabelType === 'volatility' && (
                <Col span={8}>
                  <Form.Item name="volWindow" label="波动窗口" style={{ marginBottom: 8 }}>
                    <Input type="number" placeholder="默认20" min={5} max={60} />
                  </Form.Item>
                </Col>
                )}
              </Row>
              )}

              <Divider style={{ margin: '12px 0' }}>特征选择</Divider>

              <div style={{ marginBottom: 8 }}>
                <Space>
                  <Button.Group>
                    <Button type={featureType === 'all' ? 'primary' : 'default'} onClick={() => handleFeatureTypeChange('all')}>全部</Button>
                    <Button type={featureType === 'technical' ? 'primary' : 'default'} onClick={() => handleFeatureTypeChange('technical')}>技术指标</Button>
                    <Button type={featureType === 'alpha191' ? 'primary' : 'default'} onClick={() => handleFeatureTypeChange('alpha191')}>Alpha191</Button>
                  </Button.Group>
                  <span style={{ color: '#888', fontSize: 12 }}>已选: {selectedFeatures.length}</span>
                </Space>
              </div>

              <Form.Item name="features" style={{ marginBottom: 0 }}>
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

              <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
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
            </Form>
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
                  <Tag color={selectedTask.type === 'batch' ? 'blue' : 'green'}>
                    {selectedTask.type === 'batch' ? '批量训练' : '单任务'}
                  </Tag>
                </Descriptions.Item>
                <Descriptions.Item label="运行模式">
                  <Tag color={selectedTask.train_mode === 'process' ? 'blue' : selectedTask.train_mode === 'single' ? 'default' : 'cyan'}>
                    {selectedTask.train_mode === 'single' ? '单线程' : selectedTask.train_mode === 'process' ? '多进程' : '多线程'}
                  </Tag>
                </Descriptions.Item>
                <Descriptions.Item label="状态">{getStatusTag(selectedTask.status)}</Descriptions.Item>
                <Descriptions.Item label="进度">{Math.round(selectedTask.progress)}%</Descriptions.Item>
                <Descriptions.Item label="已处理">{selectedTask.processed_count} / {selectedTask.total_count}</Descriptions.Item>
                <Descriptions.Item label="成功数">{selectedTask.success_count || 0}</Descriptions.Item>
                <Descriptions.Item label="失败数">{selectedTask.fail_count || 0}</Descriptions.Item>
                {selectedTask.stocks && selectedTask.stocks.length > 0 && (
                  <Descriptions.Item label="股票列表" span={2}>
                    <div style={{ maxHeight: 100, overflow: 'auto' }}>
                      {selectedTask.stocks.slice(0, 50).map((stock, idx) => (
                        <Tag key={idx} size="small" style={{ margin: 2 }}>{stock}</Tag>
                      ))}
                      {selectedTask.stocks.length > 50 && <span style={{ color: '#888' }}>... 共 {selectedTask.stocks.length} 只</span>}
                    </div>
                  </Descriptions.Item>
                )}
                <Descriptions.Item label="开始时间">
                  {selectedTask.start_time ? new Date(selectedTask.start_time * 1000).toLocaleString() : '-'}
                </Descriptions.Item>
                <Descriptions.Item label="耗时">
                  {selectedTask.elapsed_time ? `${Math.round(selectedTask.elapsed_time)}秒` : '-'}
                </Descriptions.Item>
                <Descriptions.Item label="消息" span={2}>{selectedTask.message || '-'}</Descriptions.Item>
                {selectedTask.params && Object.keys(selectedTask.params).length > 0 && (
                  <Descriptions.Item label="参数配置" span={2}>
                    <div style={{ fontSize: 12 }}>
                      {selectedTask.params.market && <span>市场: {selectedTask.params.market} | </span>}
                      {selectedTask.params.period && <span>周期: {selectedTask.params.period} | </span>}
                      {selectedTask.params.model_type && <span>模型: {selectedTask.params.model_type} | </span>}
                      {selectedTask.params.horizon && <span>预测天数: {selectedTask.params.horizon} | </span>}
                      {selectedTask.params.threshold && <span>阈值: {selectedTask.params.threshold * 100}%</span>}
                    </div>
                  </Descriptions.Item>
                )}
              </Descriptions>
            )}
          </Modal>
        </Tabs.TabPane>

        <Tabs.TabPane tab={<span style={{ color: '#fff' }}>增量训练</span>} key="2">
          <Card>
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

              <Button type="primary" htmlType="submit" icon={<CloudUploadOutlined />} loading={loading} style={{ width: '100%' }}>
                增量训练
              </Button>
            </Space>
          </Form>
          </Card>
        </Tabs.TabPane>

        <Tabs.TabPane tab={<span style={{ color: '#fff' }}>预测</span>} key="3">
          <Card>
            <Form layout="vertical" onFinish={handlePredict}>
            <Space direction="vertical" style={{ width: '100%' }}>
              <Form.Item name="data_source" label="数据源" initialValue="akshare" style={{ marginBottom: 8 }}>
                <Select>
                  <Select.Option value="akshare">AKShare (实时数据)</Select.Option>
                  <Select.Option value="factor_cache">因子缓存 (本地缓存)</Select.Option>
                </Select>
              </Form.Item>

              <Form.Item name="predict_date" label="预测日期" style={{ marginBottom: 8 }}>
                <DatePicker 
                  placeholder="留空则使用最新数据预测" 
                  format="YYYYMMDD" 
                  style={{ width: '100%' }}
                />
              </Form.Item>

              <Form.Item name="model_id" label="选择模型" rules={[{ required: true }]} style={{ marginBottom: 8 }}>
                <Select placeholder="选择模型">
                  {Object.entries(ensembleGroups).map(([parentId, group]) => {
                    const m = group[0]
                    return (
                      <Select.Option key={parentId} value={parentId}>
                        {m.model_name} [{m.model_type}]
                      </Select.Option>
                    )
                  })}
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
          </Card>
        </Tabs.TabPane>

        <Tabs.TabPane tab={<span style={{ color: '#fff' }}>选股</span>} key="advanced">
          <Space direction="vertical" style={{ width: '100%' }} size="middle">
            <Card title="预测配置" size="small">
              <Form layout="vertical" onFinish={handleAdvancedPredict}>
                <Form.Item name="data_source" label="数据源" initialValue="factor_cache">
                  <Select>
                    <Select.Option value="akshare">AKShare (实时数据)</Select.Option>
                    <Select.Option value="local">本地数据 (CSV文件)</Select.Option>
                    <Select.Option value="factor_cache">因子缓存 (本地缓存)</Select.Option>
                  </Select>
                </Form.Item>

                <Form.Item shouldUpdate={(prevValues, currentValues) => prevValues.data_source !== currentValues.data_source}>
                  {({ getFieldValue }) => {
                    const dataSource = getFieldValue('data_source');
                    return dataSource === 'akshare' ? (
                      <>
                        <Form.Item name="markets" label="选择市场" initialValue={['SZ']}>
                          <Checkbox.Group>
                            <Checkbox value="SZ">深圳(SZ)</Checkbox>
                            <Checkbox value="SH">上海(SH)</Checkbox>
                            <Checkbox value="BJ">北京(BJ)</Checkbox>
                          </Checkbox.Group>
                        </Form.Item>
                        <Form.Item name="stocks" label="特定股票">
                          <Input placeholder="输入股票代码，多个用逗号分隔(可选)" />
                        </Form.Item>
                      </>
                    ) : (
                      <Form.Item name="markets" label="选择市场" initialValue={['SZ']}>
                        <Checkbox.Group>
                          <Checkbox value="SZ">深圳(SZ)</Checkbox>
                          <Checkbox value="SH">上海(SH)</Checkbox>
                          <Checkbox value="BJ">北京(BJ)</Checkbox>
                        </Checkbox.Group>
                      </Form.Item>
                    );
                  }}
                </Form.Item>

                <Form.Item name="model_ids" label="选择模型" rules={[{ required: true }]}>
                  <Select mode="multiple" placeholder="选择多个模型">
                    {Object.entries(ensembleGroups).map(([parentId, group]) => {
                      const m = group[0]
                      return (
                        <Select.Option key={parentId} value={parentId}>
                          {m.model_name} [{m.model_type}]
                        </Select.Option>
                      )
                    })}
                    {Array.isArray(models) && models.map(m => (
                      <Select.Option key={m.id || m.model_name} value={m.id || m.model_name}>
                        {m.model_name || m.id} [{m.model_type || ''}]
                      </Select.Option>
                    ))}
                  </Select>
                </Form.Item>

                <Row gutter={8}>
                  <Col span={12}>
                    <Form.Item name="sort_by" label="排序依据" initialValue="return">
                      <Select>
                        <Select.Option value="confidence">置信度</Select.Option>
                        <Select.Option value="buy_probability">买入概率</Select.Option>
                        <Select.Option value="return">预测收益率</Select.Option>
                      </Select>
                    </Form.Item>
                  </Col>
                  <Col span={12}>
                    <Form.Item name="sort_order" label="排序顺序" initialValue="desc">
                      <Select>
                        <Select.Option value="desc">降序</Select.Option>
                        <Select.Option value="asc">升序</Select.Option>
                      </Select>
                    </Form.Item>
                  </Col>
                </Row>

                <Row gutter={8}>
                  <Col span={12}>
                    <Form.Item name="top_n" label="结果数量" initialValue={100}>
                      <Input type="number" min={1} max={1000} />
                    </Form.Item>
                  </Col>
                  <Col span={12}>
                    <Form.Item name="fusion_mode" label="融合模式" initialValue="intersection">
                      <Select>
                        <Select.Option value="intersection">交集(多模型一致)</Select.Option>
                        <Select.Option value="union">并集(任一模型看好)</Select.Option>
                        <Select.Option value="weighted">加权投票</Select.Option>
                      </Select>
                    </Form.Item>
                  </Col>
                </Row>

                <Form.Item name="period" label="周期" initialValue="1d">
                  <Select>
                    <Select.Option value="1d">日线</Select.Option>
                    <Select.Option value="1w">周线</Select.Option>
                    <Select.Option value="1m">月线</Select.Option>
                  </Select>
                </Form.Item>

                <Form.Item name="predict_date" label="预测日期" tooltip="留空则使用最新数据">
                  <DatePicker style={{ width: '100%' }} placeholder="留空使用最新数据" defaultValue={dayjs()} />
                </Form.Item>

                <Button
                  type="primary"
                  htmlType="submit"
                  icon={<RobotOutlined />}
                  loading={advancedPredictLoading}
                  style={{ width: '100%' }}
                >
                  开始选股
                </Button>
              </Form>
            </Card>

            <Card title="任务列表" size="small">
              <Table
                size="small"
                dataSource={advancedPredictTasks}
                rowKey="task_id"
                pagination={false}
                columns={[
                  { title: '任务ID', dataIndex: 'task_id', width: 80 },
                  { title: '状态', dataIndex: 'status', width: 80, render: v => {
                    const colorMap = { 'pending': 'default', 'running': 'processing', 'completed': 'success', 'failed': 'error', 'stopped': 'warning', 'stopping': 'processing' }
                    return <Tag color={colorMap[v] || 'default'}>{v}</Tag>
                  }},
                  { title: '进度', dataIndex: 'progress', width: 100, render: v => <Progress percent={v} size="small" /> },
                  { title: '消息', dataIndex: 'message', ellipsis: true },
                  { title: '股票数', dataIndex: 'total_stocks', width: 70 },
                  { title: '模型数', dataIndex: 'model_count', width: 70 },
                  { title: '耗时', dataIndex: 'elapsed_time', width: 70, render: v => `${v}s` },
                  { title: '操作', width: 160, render: (_, record) => (
                    <Space size={4}>
                      {record.status === 'completed' && (
                        <Button size="small" type="primary" icon={<DownloadOutlined />} onClick={() => handleViewAdvancedPredictResult(record.task_id)}>结果</Button>
                      )}
                      {(record.status === 'running' || record.status === 'stopping') && (
                        <Button size="small" danger onClick={() => handleStopAdvancedPredict(record.task_id)}>停止</Button>
                      )}
                      {record.status !== 'running' && record.status !== 'stopping' && (
                        <Button size="small" danger onClick={() => handleDeleteAdvancedPredict(record.task_id)}>删除</Button>
                      )}
                    </Space>
                  )}
                ]}
              />
            </Card>

            {advancedPredictResults && (
              <Card title="预测结果" size="small">
                {renderAdvancedPredictionResult()}
              </Card>
            )}
          </Space>
        </Tabs.TabPane>

        <Tabs.TabPane tab={<span style={{ color: '#fff' }}>已训练模型</span>} key="5">
          <Card>
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
          </Card>
        </Tabs.TabPane>

        <Tabs.TabPane tab={<span style={{ color: '#fff' }}>评估</span>} key="evaluate">
          <Space direction="vertical" style={{ width: '100%' }} size="middle">
            <Card title="评估配置" size="small">
              <Form layout="vertical" onFinish={handleEvaluate}>
                <Form.Item name="model_id" label="选择模型" rules={[{ required: true, message: '请选择模型' }]}>
                  <Select
                    placeholder="选择模型"
                    onChange={handleEvaluateModelChange}
                    showSearch
                    optionFilterProp="children"
                  >
                    {Object.entries(ensembleGroups).map(([parentId, group]) => {
                      const m = group[0]
                      return (
                        <Select.Option key={parentId} value={parentId}>
                          {m.model_name} [{m.model_type}]
                        </Select.Option>
                      )
                    })}
                    {Array.isArray(models) && models.map(m => (
                      <Select.Option key={m.id || m.model_name} value={m.id || m.model_name}>
                        {m.model_name || m.id} [{m.model_type || ''}]
                      </Select.Option>
                    ))}
                  </Select>
                </Form.Item>

                <Form.Item label="预测天数">
                  <Input value={evaluateHorizon || '-'} readOnly placeholder="选择模型后自动填充" />
                </Form.Item>

                <Form.Item name="sectors" label="选择板块" rules={[{ required: true, message: '请选择板块' }]}>
                  <TreeSelect
                    treeData={evaluateSectors}
                    fieldNames={{ label: 'title', key: 'key', value: 'key', children: 'children' }}
                    treeCheckable
                    showCheckedStrategy={TreeSelect.SHOW_CHILD}
                    placeholder="选择板块"
                    style={{ width: '100%' }}
                    maxTagCount={5}
                    dropdownStyle={{ maxHeight: 400, overflow: 'auto' }}
                    allowClear
                    treeDefaultExpandAll={false}
                    showSearch
                    treeNodeFilterProp="title"
                  />
                </Form.Item>

                <Row gutter={8}>
                  <Col span={12}>
                    <Form.Item name="start_date" label="开始日期" rules={[{ required: true, message: '请选择开始日期' }]}>
                      <DatePicker style={{ width: '100%' }} />
                    </Form.Item>
                  </Col>
                  <Col span={12}>
                    <Form.Item name="end_date" label="结束日期" rules={[{ required: true, message: '请选择结束日期' }]}>
                      <DatePicker style={{ width: '100%' }} />
                    </Form.Item>
                  </Col>
                </Row>

                <Form.Item name="validation_ratio" label="验证集比例" initialValue={20}>
                  <Slider
                    min={5}
                    max={50}
                    step={5}
                    marks={{ 5: '5%', 10: '10%', 20: '20%', 30: '30%', 50: '50%' }}
                    tooltip={{ formatter: v => `${v}%` }}
                  />
                </Form.Item>

                {evaluateLoading && (
                  <div style={{ marginBottom: 16 }}>
                    <Progress percent={evaluateProgress} status="active" />
                  </div>
                )}

                <Button
                  type="primary"
                  htmlType="submit"
                  icon={<RobotOutlined />}
                  loading={evaluateLoading}
                  style={{ width: '100%' }}
                >
                  开始评估
                </Button>
              </Form>
            </Card>

            {evaluateResults && (
              <Card title="评估结果" size="small">
                <Descriptions size="small" column={3} style={{ marginBottom: 12 }}>
                  <Descriptions.Item label="模型">{evaluateResults.model_name || evaluateResults.model_id}</Descriptions.Item>
                  <Descriptions.Item label="模式">{evaluateResults.mode === 'regression' ? '回归' : '分类'}</Descriptions.Item>
                  <Descriptions.Item label="耗时">{evaluateResults.elapsed_time}秒</Descriptions.Item>
                  <Descriptions.Item label="测试集样本">{evaluateResults.details?.test_samples || 0}</Descriptions.Item>
                  <Descriptions.Item label="验证集样本">{evaluateResults.details?.validation_samples || 0}</Descriptions.Item>
                  <Descriptions.Item label="股票数">{evaluateResults.details?.processed_stocks || 0}</Descriptions.Item>
                </Descriptions>
                {renderEvaluateMetrics(evaluateResults.test_metrics, '测试集指标')}
                {renderEvaluateMetrics(evaluateResults.validation_metrics, '验证集指标')}
              </Card>
            )}

            <Card title="评估任务列表" size="small">
              <Table
                size="small"
                dataSource={evaluateTasks}
                rowKey="task_id"
                pagination={false}
                columns={[
                  { title: '任务ID', dataIndex: 'task_id', width: 80 },
                  { title: '模型', dataIndex: 'model_name', width: 120, ellipsis: true },
                  { title: '模式', dataIndex: 'mode', width: 60, render: v => v === 'regression' ? '回归' : '分类' },
                  { title: '状态', dataIndex: 'status', width: 80, render: v => {
                    const colorMap = { 'pending': 'default', 'running': 'processing', 'completed': 'success', 'failed': 'error' }
                    return <Tag color={colorMap[v] || 'default'}>{v}</Tag>
                  }},
                  { title: '进度', dataIndex: 'progress', width: 100, render: v => <Progress percent={v} size="small" /> },
                  { title: '消息', dataIndex: 'message', ellipsis: true },
                  { title: '耗时', dataIndex: 'elapsed_time', width: 70, render: v => v ? `${v}s` : '-' },
                  { title: '操作', width: 80, render: (_, record) => (
                    <Space size={4}>
                      {record.status === 'completed' && (
                        <Button size="small" type="primary" onClick={() => handleViewEvaluateResult(record.task_id)}>结果</Button>
                      )}
                    </Space>
                  )}
                ]}
              />
            </Card>
          </Space>
        </Tabs.TabPane>
      </Tabs>
    </div>
  )
}

export default MLPanel
