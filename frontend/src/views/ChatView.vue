<script setup>
import { ref, nextTick, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import request from '../api/request'
import { useAuthStore } from '../store/auth'

const auth = useAuthStore()

// ===== 会话列表 =====
const conversations = ref([])
const currentConvId = ref(null)
const messages = ref([])
const loading = ref(false)
const sending = ref(false)

// ===== 输入 =====
const inputText = ref('')
const inputRef = ref(null)

// ===== 消息区滚动 =====
const msgAreaRef = ref(null)

function scrollToBottom() {
  nextTick(() => {
    if (msgAreaRef.value) {
      msgAreaRef.value.scrollTop = msgAreaRef.value.scrollHeight
    }
  })
}

// ===== 会话管理 =====
async function loadConversations() {
  try {
    const res = await request.get('/conversations')
    conversations.value = res
    if (conversations.value.length > 0 && !currentConvId.value) {
      await openConversation(conversations.value[0].id)
    }
  } catch (e) {}
}

async function newConversation() {
  try {
    const res = await request.post('/conversations', { title: '新对话' })
    conversations.value.unshift(res)
    await openConversation(res.id)
  } catch (e) {}
}

async function openConversation(id) {
  currentConvId.value = id
  messages.value = []
  try {
    const res = await request.get(`/conversations/${id}/messages`)
    // 解析引用来源（JSON字符串 → 对象）
    messages.value = res.map((m) => ({
      ...m,
      sources: m.sources ? JSON.parse(m.sources) : [],
    }))
    scrollToBottom()
  } catch (e) {}
}

async function deleteConversation(id) {
  await request.delete(`/conversations/${id}`)
  conversations.value = conversations.value.filter((c) => c.id !== id)
  if (currentConvId.value === id) {
    currentConvId.value = null
    messages.value = []
  }
  ElMessage.success('会话已删除')
}

// ===== 发送问题（流式）=====
async function sendMessage() {
  const text = inputText.value.trim()
  if (!text || sending.value) return
  if (!currentConvId.value) {
    ElMessage.warning('请先新建会话')
    return
  }

  // 1. 先把用户问题显示到界面（乐观更新）
  const userMsg = { id: `temp-${Date.now()}`, role: 'user', content: text, sources: [] }
  messages.value.push(userMsg)
  // 2. 添加一个空的助手消息，流式填充
  const assistantMsg = { id: `temp-${Date.now() + 1}`, role: 'assistant', content: '', sources: [], streaming: true }
  messages.value.push(assistantMsg)
  inputText.value = ''
  sending.value = true
  scrollToBottom()

  try {
    // 用 fetch 读取 SSE 流
    const token = auth.token
    const resp = await fetch('/api/chat/stream', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ conversation_id: currentConvId.value, message: text }),
    })

    if (!resp.ok || !resp.body) {
      throw new Error(`请求失败: ${resp.status}`)
    }

    // 读取流数据
    const reader = resp.body.getReader()
    const decoder = new TextDecoder('utf-8')
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })

      // 按 SSE 格式（\n\n）切分事件
      const events = buffer.split('\n\n')
      buffer = events.pop() // 最后一段可能不完整，留到下次

      for (const evt of events) {
        if (!evt.startsWith('data: ')) continue
        const data = JSON.parse(evt.slice(6))
        if (data.type === 'sources') {
          assistantMsg.sources = data.sources
        } else if (data.type === 'content') {
          assistantMsg.content += data.delta
          scrollToBottom()
        } else if (data.type === 'done') {
          assistantMsg.streaming = false
          assistantMsg.id = `done-${Date.now()}`
        }
      }
    }
  } catch (e) {
    assistantMsg.content += '\n（请求出错，请重试）'
    ElMessage.error('发送失败，请重试')
  } finally {
    assistantMsg.streaming = false
    sending.value = false
    scrollToBottom()
    // 刷新会话列表（标题可能已自动更新）
    loadConversations()
  }
}

onMounted(loadConversations)
</script>

<template>
  <div class="chat-page">
    <!-- 左侧：会话列表 -->
    <div class="conv-sidebar">
      <el-button type="primary" class="new-btn" @click="newConversation">
        + 新建会话
      </el-button>
      <div class="conv-list">
        <div
          v-for="conv in conversations"
          :key="conv.id"
          class="conv-item"
          :class="{ active: conv.id === currentConvId }"
          @click="openConversation(conv.id)"
        >
          <span class="conv-title">{{ conv.title }}</span>
          <el-icon class="del-icon" @click.stop="deleteConversation(conv.id)">
            <Delete />
          </el-icon>
        </div>
        <el-empty v-if="conversations.length === 0" description="暂无会话" :image-size="60" />
      </div>
    </div>

    <!-- 右侧：消息区 -->
    <div class="chat-main">
      <div class="message-area" ref="msgAreaRef">
        <el-empty v-if="messages.length === 0" description="从知识库中查找答案，开始你的第一个问题吧" />
        <div
          v-for="msg in messages"
          :key="msg.id"
          class="message-row"
          :class="msg.role"
        >
          <div class="message-bubble" :class="msg.role">
            <div class="message-content">{{ msg.content }}<span v-if="msg.streaming" class="cursor">▍</span></div>

            <!-- 引用来源（仅助手消息展示） -->
            <div v-if="msg.role === 'assistant' && msg.sources && msg.sources.length > 0" class="sources-box">
              <div class="sources-title">
                📚 引用来源 ({{ msg.sources.length }})
              </div>
              <el-collapse>
                <el-collapse-item
                  v-for="(src, i) in msg.sources"
                  :key="i"
                  :title="`《${src.metadata?.filename || '未知文档'}》`"
                >
                  <div class="source-content">{{ src.content }}</div>
                </el-collapse-item>
              </el-collapse>
            </div>
          </div>
        </div>
      </div>

      <!-- 输入区 -->
      <div class="input-area">
        <el-input
          ref="inputRef"
          v-model="inputText"
          type="textarea"
          :rows="2"
          :disabled="sending"
          placeholder="请输入你的问题，Enter 发送，Shift+Enter 换行"
          resize="none"
          @keydown.enter.exact.prevent="sendMessage"
        />
        <el-button
          type="primary"
          :loading="sending"
          :disabled="!inputText.trim()"
          @click="sendMessage"
        >
          发送
        </el-button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.chat-page {
  display: flex;
  height: 100%;
}

.conv-sidebar {
  width: 240px;
  border-right: 1px solid #e5e7eb;
  background: #fff;
  display: flex;
  flex-direction: column;
  padding: 12px;
  gap: 12px;
}

.new-btn {
  width: 100%;
}

.conv-list {
  flex: 1;
  overflow-y: auto;
}

.conv-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  border-radius: 6px;
  cursor: pointer;
  margin-bottom: 4px;
  color: #333;
}

.conv-item:hover {
  background: #f5f7fa;
}

.conv-item.active {
  background: #ecf5ff;
  color: #2563eb;
}

.conv-title {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 14px;
}

.del-icon {
  color: #c0c4cc;
  opacity: 0;
  transition: opacity 0.2s;
}

.conv-item:hover .del-icon {
  opacity: 1;
}

.del-icon:hover {
  color: #f56c6c;
}

.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: #f5f7fa;
}

.message-area {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

.message-row {
  display: flex;
  margin-bottom: 16px;
}

.message-row.user {
  justify-content: flex-end;
}

.message-row.assistant {
  justify-content: flex-start;
}

.message-bubble {
  max-width: 72%;
  padding: 12px 16px;
  border-radius: 10px;
}

.message-bubble.user {
  background: #2563eb;
  color: #fff;
}

.message-bubble.assistant {
  background: #fff;
  color: #333;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.cursor {
  animation: blink 0.8s infinite;
  color: #2563eb;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

.sources-box {
  margin-top: 10px;
  border-top: 1px dashed #e5e7eb;
  padding-top: 8px;
}

.sources-title {
  font-size: 12px;
  color: #909399;
  margin-bottom: 6px;
}

.source-content {
  font-size: 13px;
  color: #666;
  white-space: pre-wrap;
  line-height: 1.6;
  max-height: 200px;
  overflow-y: auto;
}

.input-area {
  padding: 12px 20px;
  background: #fff;
  border-top: 1px solid #e5e7eb;
  display: flex;
  gap: 12px;
  align-items: flex-end;
}

.input-area :deep(.el-textarea__inner) {
  font-size: 14px;
}
</style>
