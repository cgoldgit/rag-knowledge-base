<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import request from '../api/request'

// ===== 文档列表 =====
const documents = ref([])
const loading = ref(false)

async function loadDocuments() {
  loading.value = true
  try {
    const res = await request.get('/kb/documents')
    documents.value = res
  } finally {
    loading.value = false
  }
}

// ===== 上传文档 =====
const uploadRef = ref(null)

async function handleUpload(options) {
  const formData = new FormData()
  formData.append('file', options.file)
  try {
    await request.post('/kb/upload', formData)
    ElMessage.success('上传成功，正在处理...')
    loadDocuments()
  } catch (e) {
    // 错误已统一处理
  }
}

// ===== 删除文档 =====
async function handleDelete(row) {
  await ElMessageBox.confirm(
    `确定要删除文档「${row.filename}」吗？删除后不可恢复。`,
    '警告',
    { type: 'warning' },
  )
  await request.delete(`/kb/documents/${row.id}`)
  ElMessage.success('删除成功')
  loadDocuments()
}

onMounted(loadDocuments)
</script>

<template>
  <div class="kb-page">
    <!-- 工具栏 -->
    <div class="toolbar">
      <el-upload
        ref="uploadRef"
        :show-file-list="false"
        :http-request="handleUpload"
        accept=".pdf,.docx,.txt,.md,.xlsx"
        :multiple="false"
      >
        <el-button type="primary" :icon="'Upload'">上传文档</el-button>
      </el-upload>
      <span class="tip">支持 PDF / Word / TXT / Markdown / Excel 格式</span>
    </div>

    <!-- 文档列表 -->
    <el-card>
      <el-table :data="documents" v-loading="loading" stripe>
        <el-table-column prop="filename" label="文件名" min-width="200" show-overflow-tooltip />
        <el-table-column prop="file_type" label="格式" width="90">
          <template #default="{ row }">
            <el-tag size="small">{{ row.file_type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="file_size" label="大小" width="110">
          <template #default="{ row }">
            {{ (row.file_size / 1024).toFixed(1) }} KB
          </template>
        </el-table-column>
        <el-table-column prop="chunk_count" label="分块数" width="90" />
        <el-table-column prop="status" label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="row.status === 'ready' ? 'success' : row.status === 'failed' ? 'danger' : 'warning'">
              {{ row.status === 'ready' ? '已就绪' : row.status === 'failed' ? '失败' : '处理中' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="上传时间" width="170">
          <template #default="{ row }">
            {{ row.created_at?.slice(0, 19) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button type="danger" size="small" link @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<style scoped>
.kb-page {
  padding: 20px;
  height: 100%;
  overflow-y: auto;
}

.toolbar {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 16px;
}

.tip {
  font-size: 13px;
  color: #909399;
}
</style>
