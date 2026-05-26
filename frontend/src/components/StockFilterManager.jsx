import React, { useState, useEffect } from 'react';
import {
  Card, Table, Button, Switch, Tag, Modal, Form, Input, Select,
  Space, message, Popconfirm, Badge, Divider, Row, Col, InputNumber,
  Dropdown, List
} from 'antd';
import {
  PlusOutlined, DeleteOutlined, EditOutlined, FilterOutlined,
  CheckCircleOutlined, CloseCircleOutlined, SaveOutlined, FolderOutlined,
  DownloadOutlined
} from '@ant-design/icons';
import axios from 'axios';

const { Option } = Select;

const StockFilterManager = ({ embedded = false }) => {
  const [filters, setFilters] = useState([]);
  const [availableTypes, setAvailableTypes] = useState([]);
  const [loading, setLoading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [editingFilter, setEditingFilter] = useState(null);
  const [form] = Form.useForm();
  
  const [savePlanModalVisible, setSavePlanModalVisible] = useState(false);
  const [loadPlanModalVisible, setLoadPlanModalVisible] = useState(false);
  const [plans, setPlans] = useState([]);
  const [planForm] = Form.useForm();

  useEffect(() => {
    loadFilters();
  }, []);

  const loadFilters = async () => {
    setLoading(true);
    try {
      const [filtersRes, typesRes] = await Promise.all([
        axios.get('http://localhost:5000/api/stock-filters'),
        axios.get('http://localhost:5000/api/stock-filters/types')
      ]);
      console.log('筛选器类型API响应:', typesRes.data);
      console.log('筛选器列表API响应:', filtersRes.data);
      setFilters(filtersRes.data.filters || []);
      setAvailableTypes(typesRes.data.types || []);
      console.log('设置availableTypes:', typesRes.data.types || []);
    } catch (err) {
      console.error('加载条件失败:', err);
      message.error('加载条件失败');
    } finally {
      setLoading(false);
    }
  };

  const loadPlans = async () => {
    try {
      const res = await axios.get('http://localhost:5000/api/selection-plans');
      setPlans(res.data.plans || []);
    } catch (err) {
      console.error('加载选股计划失败:', err);
      message.error('加载选股计划失败');
    }
  };

  const handleToggle = async (filterId) => {
    try {
      await axios.post(`http://localhost:5000/api/stock-filters/${filterId}/toggle`);
      message.success('状态已更新');
      loadFilters();
    } catch (err) {
      message.error('更新失败');
    }
  };

  const handleDelete = async (filterId) => {
    try {
      await axios.delete(`http://localhost:5000/api/stock-filters/${filterId}`);
      message.success('已删除');
      loadFilters();
    } catch (err) {
      message.error('删除失败');
    }
  };

  const handleAdd = () => {
    setEditingFilter(null);
    form.resetFields();
    setModalVisible(true);
  };

  const handleEdit = (record) => {
    setEditingFilter(record);
    form.setFieldsValue(record);
    setModalVisible(true);
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      
      if (editingFilter) {
        await axios.put(`http://localhost:5000/api/stock-filters/${editingFilter.id}`, values);
        message.success('已更新');
      } else {
        await axios.post('http://localhost:5000/api/stock-filters', values);
        message.success('已创建');
      }
      
      setModalVisible(false);
      loadFilters();
    } catch (err) {
      message.error(err.response?.data?.error || '操作失败');
    }
  };

  const handleSavePlan = () => {
    const enabledFilters = filters.filter(f => f.enabled);
    if (enabledFilters.length === 0) {
      message.warning('请先启用至少一个筛选条件');
      return;
    }
    planForm.resetFields();
    setSavePlanModalVisible(true);
  };

  const handleSavePlanSubmit = async () => {
    try {
      const values = await planForm.validateFields();
      const enabledFilters = filters.filter(f => f.enabled);
      
      await axios.post('http://localhost:5000/api/selection-plans', {
        name: values.name,
        description: values.description,
        filters: enabledFilters
      });
      
      message.success('选股计划已保存');
      setSavePlanModalVisible(false);
    } catch (err) {
      message.error(err.response?.data?.error || '保存失败');
    }
  };

  const handleLoadPlan = async () => {
    await loadPlans();
    setLoadPlanModalVisible(true);
  };

  const handleApplyPlan = async (planId) => {
    try {
      const res = await axios.post(`http://localhost:5000/api/selection-plans/${planId}/apply`);
      message.success(`已加载 ${res.data.applied_count} 个筛选条件`);
      setLoadPlanModalVisible(false);
      loadFilters();
    } catch (err) {
      message.error(err.response?.data?.error || '加载失败');
    }
  };

  const handleDeletePlan = async (planId) => {
    try {
      await axios.delete(`http://localhost:5000/api/selection-plans/${planId}`);
      message.success('已删除');
      loadPlans();
    } catch (err) {
      message.error('删除失败');
    }
  };

  const getCategoryTag = (category) => {
    const colors = {
      technical: 'blue',
      fundamental: 'green',
      custom: 'orange'
    };
    const labels = {
      technical: '技术指标',
      fundamental: '基本面',
      custom: '自定义'
    };
    return <Tag color={colors[category] || 'default'}>{labels[category] || category}</Tag>;
  };

  const getStageTag = (stage) => {
    const colors = {
      pre_filter: 'purple',
      post_filter: 'cyan'
    };
    const labels = {
      pre_filter: '预筛选',
      post_filter: '后筛选'
    };
    return <Tag color={colors[stage] || 'default'}>{labels[stage] || stage}</Tag>;
  };

  const columns = [
    {
      title: '启用',
      dataIndex: 'enabled',
      key: 'enabled',
      width: 80,
      render: (enabled, record) => (
        <Switch
          checked={enabled}
          onChange={() => handleToggle(record.id)}
          size="small"
        />
      )
    },
    {
      title: '条件名称',
      dataIndex: 'name',
      key: 'name',
      width: 150
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true
    },
    {
      title: '分类',
      dataIndex: 'category',
      key: 'category',
      width: 100,
      render: getCategoryTag
    },
    {
      title: '阶段',
      dataIndex: 'filter_stage',
      key: 'filter_stage',
      width: 100,
      render: getStageTag
    },
    {
      title: '条件类型',
      dataIndex: 'condition_type',
      key: 'condition_type',
      width: 120
    },
    {
      title: '操作',
      key: 'action',
      width: 120,
      render: (_, record) => (
        <Space size="small">
          <Button
            type="link"
            size="small"
            icon={<EditOutlined />}
            onClick={() => handleEdit(record)}
          />
          <Popconfirm
            title="确定删除此条件？"
            onConfirm={() => handleDelete(record.id)}
            okText="确定"
            cancelText="取消"
          >
            <Button
              type="link"
              size="small"
              danger
              icon={<DeleteOutlined />}
            />
          </Popconfirm>
        </Space>
      )
    }
  ];

  const selectedType = Form.useWatch('condition_type', form);
  const selectedTypeInfo = availableTypes.find(t => t.filter_id === selectedType);

  const planButtons = (
    <Space>
      <Button 
        icon={<SaveOutlined />} 
        onClick={handleSavePlan}
        disabled={filters.filter(f => f.enabled).length === 0}
      >
        保存计划
      </Button>
      <Button 
        icon={<FolderOutlined />} 
        onClick={handleLoadPlan}
      >
        加载计划
      </Button>
    </Space>
  );

  const content = (
    <>
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Button type="primary" icon={<PlusOutlined />} onClick={handleAdd}>
          添加条件
        </Button>
        {planButtons}
        <span style={{ marginLeft: 16, color: '#888' }}>
          已启用 {filters.filter(f => f.enabled).length} 个条件
        </span>
      </div>
      <Table
        columns={columns}
        dataSource={filters}
        rowKey="id"
        loading={loading}
        pagination={false}
        size="small"
        locale={{ emptyText: '暂无条件，请添加' }}
      />

      <Modal
        title={editingFilter ? '编辑条件' : '添加条件'}
        open={modalVisible}
        onOk={handleSubmit}
        onCancel={() => setModalVisible(false)}
        okText="保存"
        cancelText="取消"
        width={600}
      >
        <Form form={form} layout="vertical">
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="name"
                label="条件名称"
                rules={[{ required: true, message: '请输入条件名称' }]}
              >
                <Input placeholder="如：均线多头排列" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="condition_type"
                label="条件类型"
                rules={[{ required: true, message: '请选择条件类型' }]}
              >
                <Select placeholder="选择条件类型">
                  {availableTypes.map(type => (
                    <Option key={type.filter_id} value={type.filter_id}>
                      {type.name} ({type.category})
                    </Option>
                  ))}
                </Select>
              </Form.Item>
            </Col>
          </Row>

          <Form.Item name="description" label="描述">
            <Input.TextArea rows={2} placeholder="条件描述" />
          </Form.Item>

          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="category" label="分类" initialValue="technical">
                <Select>
                  <Option value="technical">技术指标</Option>
                  <Option value="fundamental">基本面</Option>
                  <Option value="custom">自定义</Option>
                </Select>
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="filter_stage" label="执行阶段" initialValue="pre_filter">
                <Select>
                  <Option value="pre_filter">预筛选（模型预测前）</Option>
                  <Option value="post_filter">后筛选（模型预测后）</Option>
                </Select>
              </Form.Item>
            </Col>
          </Row>

          <Form.Item name="priority" label="优先级" initialValue={0}>
            <InputNumber min={0} max={100} style={{ width: '100%' }} />
          </Form.Item>

          {selectedTypeInfo?.parameters_schema?.properties && (
            <>
              <Divider>条件参数</Divider>
              {Object.entries(selectedTypeInfo.parameters_schema.properties).map(([key, schema]) => (
                <Form.Item
                  key={key}
                  name={['parameters', key]}
                  label={schema.title || key}
                  initialValue={schema.default}
                >
                  {schema.enum ? (
                    <Select placeholder={`选择${schema.title || key}`}>
                      {schema.enum.map(v => <Option key={v} value={v}>{v}</Option>)}
                    </Select>
                  ) : schema.type === 'integer' || schema.type === 'number' ? (
                    <InputNumber 
                      min={schema.minimum} 
                      max={schema.maximum} 
                      step={schema.type === 'number' ? 0.1 : 1}
                      style={{ width: '100%' }} 
                    />
                  ) : schema.type === 'array' && schema.items?.enum ? (
                    <Select mode="multiple" placeholder={`选择${schema.title || key}`}>
                      {schema.items.enum.map(v => <Option key={v} value={v}>{v}</Option>)}
                    </Select>
                  ) : schema.type === 'array' ? (
                    <Select mode="tags" placeholder="输入后回车添加">
                      {schema.default?.map(v => <Option key={v} value={v}>{v}</Option>)}
                    </Select>
                  ) : (
                    <Input />
                  )}
                </Form.Item>
              ))}
            </>
          )}
        </Form>
      </Modal>

      <Modal
        title="保存选股计划"
        open={savePlanModalVisible}
        onOk={handleSavePlanSubmit}
        onCancel={() => setSavePlanModalVisible(false)}
        okText="保存"
        cancelText="取消"
      >
        <Form form={planForm} layout="vertical">
          <Form.Item
            name="name"
            label="计划名称"
            rules={[{ required: true, message: '请输入计划名称' }]}
          >
            <Input placeholder="如：趋势跟踪策略" />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={3} placeholder="计划描述" />
          </Form.Item>
          <div style={{ color: '#888', fontSize: 12 }}>
            将保存当前已启用的 {filters.filter(f => f.enabled).length} 个筛选条件
          </div>
        </Form>
      </Modal>

      <Modal
        title="加载选股计划"
        open={loadPlanModalVisible}
        onCancel={() => setLoadPlanModalVisible(false)}
        footer={null}
        width={500}
      >
        {plans.length === 0 ? (
          <div style={{ textAlign: 'center', padding: 20, color: '#888' }}>
            暂无保存的计划
          </div>
        ) : (
          <List
            dataSource={plans}
            renderItem={plan => (
              <List.Item
                actions={[
                  <Button 
                    type="link" 
                    size="small"
                    icon={<DownloadOutlined />}
                    onClick={() => handleApplyPlan(plan.id)}
                  >
                    加载
                  </Button>,
                  <Popconfirm
                    title="确定删除此计划？"
                    onConfirm={() => handleDeletePlan(plan.id)}
                    okText="确定"
                    cancelText="取消"
                  >
                    <Button type="link" size="small" danger icon={<DeleteOutlined />} />
                  </Popconfirm>
                ]}
              >
                <List.Item.Meta
                  title={plan.name}
                  description={
                    <div>
                      <div>{plan.description || '无描述'}</div>
                      <div style={{ fontSize: 12, color: '#888' }}>
                        {plan.filters?.length || 0} 个筛选条件 · 
                        创建于 {new Date(plan.created_at).toLocaleString()}
                      </div>
                    </div>
                  }
                />
              </List.Item>
            )}
          />
        )}
      </Modal>
    </>
  );

  if (embedded) {
    return content;
  }

  return (
    <Card
      title={
        <Space>
          <FilterOutlined />
          选股条件管理
          <Badge count={filters.filter(f => f.enabled).length} style={{ backgroundColor: '#52c41a' }} />
        </Space>
      }
      extra={
        <Space>
          {planButtons}
          <Button type="primary" icon={<PlusOutlined />} onClick={handleAdd}>
            添加条件
          </Button>
        </Space>
      }
    >
      <Table
        columns={columns}
        dataSource={filters}
        rowKey="id"
        loading={loading}
        pagination={false}
        size="small"
        locale={{ emptyText: '暂无条件，请添加' }}
      />

      <Modal
        title={editingFilter ? '编辑条件' : '添加条件'}
        open={modalVisible}
        onOk={handleSubmit}
        onCancel={() => setModalVisible(false)}
        okText="保存"
        cancelText="取消"
        width={600}
      >
        <Form form={form} layout="vertical">
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="name"
                label="条件名称"
                rules={[{ required: true, message: '请输入条件名称' }]}
              >
                <Input placeholder="如：均线多头排列" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="condition_type"
                label="条件类型"
                rules={[{ required: true, message: '请选择条件类型' }]}
              >
                <Select placeholder="选择条件类型">
                  {availableTypes.map(type => (
                    <Option key={type.filter_id} value={type.filter_id}>
                      {type.name} ({type.category})
                    </Option>
                  ))}
                </Select>
              </Form.Item>
            </Col>
          </Row>

          <Form.Item name="description" label="描述">
            <Input.TextArea rows={2} placeholder="条件描述" />
          </Form.Item>

          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="category" label="分类" initialValue="technical">
                <Select>
                  <Option value="technical">技术指标</Option>
                  <Option value="fundamental">基本面</Option>
                  <Option value="custom">自定义</Option>
                </Select>
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="filter_stage" label="执行阶段" initialValue="pre_filter">
                <Select>
                  <Option value="pre_filter">预筛选（模型预测前）</Option>
                  <Option value="post_filter">后筛选（模型预测后）</Option>
                </Select>
              </Form.Item>
            </Col>
          </Row>

          <Form.Item name="priority" label="优先级" initialValue={0}>
            <InputNumber min={0} max={100} style={{ width: '100%' }} />
          </Form.Item>

          {selectedTypeInfo?.parameters_schema?.properties && (
            <>
              <Divider>条件参数</Divider>
              {Object.entries(selectedTypeInfo.parameters_schema.properties).map(([key, schema]) => (
                <Form.Item
                  key={key}
                  name={['parameters', key]}
                  label={schema.title || key}
                  initialValue={schema.default}
                >
                  {schema.enum ? (
                    <Select placeholder={`选择${schema.title || key}`}>
                      {schema.enum.map(v => <Option key={v} value={v}>{v}</Option>)}
                    </Select>
                  ) : schema.type === 'integer' || schema.type === 'number' ? (
                    <InputNumber 
                      min={schema.minimum} 
                      max={schema.maximum} 
                      step={schema.type === 'number' ? 0.1 : 1}
                      style={{ width: '100%' }} 
                    />
                  ) : schema.type === 'array' && schema.items?.enum ? (
                    <Select mode="multiple" placeholder={`选择${schema.title || key}`}>
                      {schema.items.enum.map(v => <Option key={v} value={v}>{v}</Option>)}
                    </Select>
                  ) : schema.type === 'array' ? (
                    <Select mode="tags" placeholder="输入后回车添加">
                      {schema.default?.map(v => <Option key={v} value={v}>{v}</Option>)}
                    </Select>
                  ) : (
                    <Input />
                  )}
                </Form.Item>
              ))}
            </>
          )}
        </Form>
      </Modal>

      <Modal
        title="保存选股计划"
        open={savePlanModalVisible}
        onOk={handleSavePlanSubmit}
        onCancel={() => setSavePlanModalVisible(false)}
        okText="保存"
        cancelText="取消"
      >
        <Form form={planForm} layout="vertical">
          <Form.Item
            name="name"
            label="计划名称"
            rules={[{ required: true, message: '请输入计划名称' }]}
          >
            <Input placeholder="如：趋势跟踪策略" />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={3} placeholder="计划描述" />
          </Form.Item>
          <div style={{ color: '#888', fontSize: 12 }}>
            将保存当前已启用的 {filters.filter(f => f.enabled).length} 个筛选条件
          </div>
        </Form>
      </Modal>

      <Modal
        title="加载选股计划"
        open={loadPlanModalVisible}
        onCancel={() => setLoadPlanModalVisible(false)}
        footer={null}
        width={500}
      >
        {plans.length === 0 ? (
          <div style={{ textAlign: 'center', padding: 20, color: '#888' }}>
            暂无保存的计划
          </div>
        ) : (
          <List
            dataSource={plans}
            renderItem={plan => (
              <List.Item
                actions={[
                  <Button 
                    type="link" 
                    size="small"
                    icon={<DownloadOutlined />}
                    onClick={() => handleApplyPlan(plan.id)}
                  >
                    加载
                  </Button>,
                  <Popconfirm
                    title="确定删除此计划？"
                    onConfirm={() => handleDeletePlan(plan.id)}
                    okText="确定"
                    cancelText="取消"
                  >
                    <Button type="link" size="small" danger icon={<DeleteOutlined />} />
                  </Popconfirm>
                ]}
              >
                <List.Item.Meta
                  title={plan.name}
                  description={
                    <div>
                      <div>{plan.description || '无描述'}</div>
                      <div style={{ fontSize: 12, color: '#888' }}>
                        {plan.filters?.length || 0} 个筛选条件 · 
                        创建于 {new Date(plan.created_at).toLocaleString()}
                      </div>
                    </div>
                  }
                />
              </List.Item>
            )}
          />
        )}
      </Modal>
    </Card>
  );
};

export default StockFilterManager;
