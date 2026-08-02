<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getSettings, saveSettings } from '../api/settings'

const topK = ref(6)
const showSources = ref(true)
const loading = ref(false)
const saving = ref(false)

async function load() {
  loading.value = true
  try {
    const res = await getSettings()
    topK.value = res.top_k ?? 6
    showSources.value = res.show_sources ?? true
  } finally {
    loading.value = false
  }
}

async function handleSave() {
  saving.value = true
  try {
    await saveSettings({
      top_k: topK.value,
      show_sources: showSources.value,
    })
    ElMessage.success('设置已保存')
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="settings-page">
    <el-card v-loading="loading" class="settings-card">
      <template #header>
        <span>个性化设置</span>
      </template>

      <el-form label-width="150px">
        <el-form-item label="回答参考片段数">
          <div class="setting-row">
            <el-slider
              v-model="topK"
              :min="1"
              :max="10"
              :step="1"
              show-input
              style="width: 260px"
            />
            <span class="hint">回答时参考知识库的片段数量（默认 6，越多越全面但越慢）</span>
          </div>
        </el-form-item>

        <el-form-item label="显示引用来源">
          <div class="setting-row">
            <el-switch v-model="showSources" />
            <span class="hint">回答下方是否显示引用的知识库片段</span>
          </div>
        </el-form-item>

        <el-form-item>
          <el-button type="primary" :loading="saving" @click="handleSave">
            保存设置
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<style scoped>
.settings-page {
  padding: 20px;
  display: flex;
  justify-content: center;
}

.settings-card {
  width: 560px;
}

.setting-row {
  display: flex;
  align-items: center;
  gap: 16px;
}

.hint {
  font-size: 12px;
  color: #909399;
}
</style>
