<script setup>
import { ref, nextTick, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import request from '../api/request'
import { rateMessage } from '../api/settings'
import { useAuthStore } from '../store/auth'

const auth = useAuthStore()

// ===== 会话列表 =====
const conversations = ref([])
const currentConvId = ref(null)
const messages = ref([])
const sending = ref(false)

// ===== 输入 =====
const inputText = ref('')
const inputRef = ref(null)

// ===== 重命名弹窗 =====
const renameDialogVisible = ref(false)
const renameTitle = ref('')

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
    messages.value = res.map((m) => ({
      ...m,
      sources: m.sources ? JSON.parse(m.sources) : [],
    }))
    scrollToBottom()
  } catch (e) {}
}

async function deleteConversation(id) {
  try {
    await ElMessageBox.confirm('删除后不可恢复，确定删除该会话？', '删除会话', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
    })
  } catch {
    return // 用户取消
  }
  await request.delete(`/conversations/${id}`)
  conversations.value = conversations.value.filter((c) => c.id !== id)
  if (currentConvId.value === id) {
    currentConvId.value = null
    messages.value = []
  }
  ElMessage.success('会话已删除')
}

async function clearConversation(id) {
  try {
    await ElMessageBox.confirm('将清空该会话的全部消息，确定继续？', '清空会话', {
      confirmButtonText: '清空',
      cancelButtonText: '取消',
      type: 'warning',
    })
  } catch {
    return
  }
  await request.delete(`/conversations/${id}/messages`)
  if (currentConvId.value === id) {
    messages.value = []
  }
  ElMessage.success('会话已清空')
  loadConversations()
}

// ===== 重命名 =====
function openRename(conv) {
  renameTitle.value = conv.title
  renameDialogVisible.value = true
}

async function handleRename() {
  if (!renameTitle.value.trim()) {
    ElMessage.warning('名称不能为空')
    return
  }
  await request.put(`/conversations/${currentConvId.value}`, { title: renameTitle.value.trim() })
  renameDialogVisible.value = false
  ElMessage.success('重命名成功')
  loadConversations()
}

// ===== 回答操作 =====
async function handleRate(msg, rating) {
  // 点击相同评价则取消
  const newRating = msg.rating === rating ? null : rating
  try {
    await rateMessage(msg.id, newRating)
    msg.rating = newRating
  } catch (e) {}
}

async function handleCopy(msg) {
  try {
    await navigator.clipboard.writeText(msg.content)
    ElMessage.success('已复制')
  } catch {
    ElMessage.error('复制失败')
  }
}

// ===== 会话操作（三点菜单）=====
async function handleConvCmd(cmd, conv) {
  if (cmd === 'pin') {
    // 置顶/取消置顶
    try {
      const res = await request.put(`/conversations/${conv.id}/pin`)
      conv.pinned = res.pinned
      ElMessage.success(res.pinned ? '已置顶' : '已取消置顶')
      // 刷新列表（置顶的排前面）
      loadConversations()
    } catch (e) {}
  } else if (cmd === 'rename') {
    renameTitle.value = conv.title
    currentConvId.value = conv.id
    renameDialogVisible.value = true
  } else if (cmd === 'clear') {
    await clearConversation(conv.id)
  } else if (cmd === 'delete') {
    await deleteConversation(conv.id)
  }
}

// ===== 发送问题（流式）=====
async function sendMessage() {
  const text = inputText.value.trim()
  if (!text || sending.value) return
  if (!currentConvId.value) {
    ElMessage.warning('请先新建会话')
    return
  }

  const userMsg = { id: `temp-u-${Date.now()}`, role: 'user', content: text, sources: [] }
  const assistantMsg = { id: `temp-a-${Date.now()}`, role: 'assistant', content: '', sources: [], streaming: true }
  messages.value.push(userMsg, assistantMsg)
  inputText.value = ''
  sending.value = true
  scrollToBottom()

  try {
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
      const err = await resp.json().catch(() => ({}))
      throw new Error(err.detail || `请求失败: ${resp.status}`)
    }

    const reader = resp.body.getReader()
    const decoder = new TextDecoder('utf-8')
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })

      const events = buffer.split('\n\n')
      buffer = events.pop()

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
        }
      }
    }
  } catch (e) {
    assistantMsg.content += `\n（${e.message || '请求出错'}）`
    ElMessage.error(e.message || '发送失败，请重试')
  } finally {
    assistantMsg.streaming = false
    sending.value = false
    scrollToBottom()
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
          <span class="conv-title">
            <el-icon v-if="conv.pinned" class="pin-icon"><Top /></el-icon>
            <span class="conv-name">{{ conv.title }}</span>
          </span>
          <div class="conv-actions" @click.stop>
            <el-dropdown trigger="click" @command="(cmd) => handleConvCmd(cmd, conv)">
              <el-icon class="more-icon" :class="{ active: conv.id === currentConvId }">
                <MoreFilled />
              </el-icon>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="pin">
                    <el-icon><Top /></el-icon>{{ conv.pinned ? '取消置顶' : '置顶' }}
                  </el-dropdown-item>
                  <el-dropdown-item command="rename">
                    <el-icon><EditPen /></el-icon>重命名
                  </el-dropdown-item>
                  <el-dropdown-item command="clear">
                    <el-icon><Delete /></el-icon>清空消息
                  </el-dropdown-item>
                  <el-dropdown-item command="delete" divided>
                    <el-icon><Delete /></el-icon>删除会话
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
        </div>
        <el-empty v-if="conversations.length === 0" description="暂无会话，点击上方新建" :image-size="60" />
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

            <!-- 助手消息操作栏 -->
            <div v-if="msg.role === 'assistant' && !msg.streaming" class="msg-actions">
              <el-tooltip content="复制回答">
                <el-icon class="action-icon" @click="handleCopy(msg)"><CopyDocument /></el-icon>
              </el-tooltip>
              <el-tooltip content="有用">
                <el-icon
                  class="action-icon"
                  :class="{ active: msg.rating === 'up' }"
                  @click="handleRate(msg, 'up')"
                ><CircleCheck /></el-icon>
              </el-tooltip>
              <el-tooltip content="没用">
                <el-icon
                  class="action-icon"
                  :class="{ active: msg.rating === 'down' }"
                  @click="handleRate(msg, 'down')"
                ><CircleClose /></el-icon>
              </el-tooltip>
            </div>

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

    <!-- 重命名弹窗 -->
    <el-dialog v-model="renameDialogVisible" title="重命名会话" width="400px">
      <el-input v-model="renameTitle" placeholder="请输入新名称" @keyup.enter="handleRename" />
      <template #footer>
        <el-button @click="renameDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleRename">确定</el-button>
      </template>
    </el-dialog>
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
  display: flex;
  align-items: center;
  gap: 4px;
  min-width: 0;
}

.conv-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 置顶标记 */
.pin-icon {
  color: #f59e0b;
  font-size: 14px;
  flex-shrink: 0;
}

.conv-actions {
  display: flex;
  align-items: center;
  margin-left: 6px;
  flex-shrink: 0;
}

/* 设置按钮（三点）：始终可见，主题蓝醒目显示 */
.more-icon {
  font-size: 17px;
  color: #2563eb;
  cursor: pointer;
  padding: 3px;
  border-radius: 5px;
  background: #eef3fc;
  transition: color 0.15s, background 0.15s, transform 0.15s;
}

.more-icon:hover {
  color: #fff;
  background: #2563eb;
  transform: scale(1.1);
}

/* 当前选中会话的三点加深 */
.more-icon.active {
  color: #fff;
  background: #2563eb;
}

/* 下拉菜单图标间距 */
.conv-actions :deep(.el-dropdown-menu__item) {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
}

.conv-actions :deep(.el-dropdown-menu__item .el-icon) {
  font-size: 15px;
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

.msg-actions {
  display: flex;
  gap: 12px;
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid #f0f0f0;
}

.action-icon {
  font-size: 16px;
  color: #c0c4cc;
  cursor: pointer;
}

.action-icon:hover {
  color: #2563eb;
}

.action-icon.active {
  color: #2563eb;
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
