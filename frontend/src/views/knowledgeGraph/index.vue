<template>
  <PageFrame
    title="知识图谱"
    code="KNOWLEDGE / GRAPH"
    description="围绕华为与阳光电源光伏逆变器检修资料，管理节点、关系、证据和规则抽取候选。"
  >
    <template #actions>
      <button class="scada-button" type="button" :disabled="loading" @click="loadAll">
        <RefreshCcw :size="16" />
        刷新
      </button>
    </template>

    <div v-if="error" class="rounded-md border border-red-400/30 bg-red-500/10 p-4 text-sm text-red-200">{{ error }}</div>

    <div class="flex flex-wrap gap-2">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        class="scada-button !min-h-9 !px-3"
        :class="{ 'border-cyan-300/60 bg-cyan-300/10 text-cyan-100': activeTab === tab.key }"
        type="button"
        @click="activeTab = tab.key"
      >
        {{ tab.label }}
      </button>
    </div>

    <section v-if="activeTab === 'overview'" class="space-y-4">
      <div class="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
        <DataPanel v-for="item in overviewCards" :key="item.label" :title="item.label">
          <div class="text-3xl font-black text-white">{{ item.value }}</div>
          <p class="mt-2 text-xs text-slate-400">{{ item.detail }}</p>
        </DataPanel>
      </div>

      <div class="grid gap-4 lg:grid-cols-2">
        <DataPanel title="节点类型分布">
          <div class="space-y-2">
            <div v-for="item in nodeTypeItems" :key="item.key" class="flex items-center justify-between gap-3 text-sm">
              <span class="text-slate-300">{{ formatKnowledgeGraphNodeType(item.key) }}</span>
              <span class="font-mono text-cyan-100">{{ item.value }}</span>
            </div>
          </div>
        </DataPanel>
        <DataPanel title="关系类型分布">
          <div class="space-y-2">
            <div v-for="item in relationTypeItems" :key="item.key" class="flex items-center justify-between gap-3 text-sm">
              <span class="text-slate-300">{{ formatKnowledgeGraphRelation(item.key) }}</span>
              <span class="font-mono text-cyan-100">{{ item.value }}</span>
            </div>
          </div>
        </DataPanel>
      </div>

      <DataPanel v-if="(overview?.node_count || 0) === 0" title="知识图谱尚未初始化" subtitle="仅会从已审核、已解析、启用的华为和阳光电源光伏逆变器文档中生成可追溯事实。">
        <div class="flex flex-wrap items-center gap-3 text-sm text-slate-300">
          <span>可用正式文档：{{ overview?.eligible_document_count || 0 }}</span>
          <span>状态：{{ overview?.initialization_status || 'NOT_INITIALIZED' }}</span>
          <button v-if="canManage" class="scada-button" type="button" :disabled="initializing || !(overview?.eligible_document_count || 0)" @click="bootstrapGraph">
            {{ initializing ? '初始化中…' : '初始化图谱' }}
          </button>
          <span v-else>图谱等待管理员或专家初始化。</span>
        </div>
      </DataPanel>
    </section>

    <section v-if="activeTab === 'graph'" class="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
      <DataPanel title="交互式图谱视图" subtitle="仅展示 active 节点和 active 关系，点击节点可查看详情，点击关系可查看 evidence。">
        <div class="mb-4 grid gap-3 md:grid-cols-3 xl:grid-cols-6">
          <select v-model="graphFilters.manufacturer" class="scada-input">
            <option value="">不限厂家</option>
            <option v-for="item in manufacturerOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
          </select>
          <select v-model="graphFilters.product_series" class="scada-input">
            <option value="">不限系列</option>
            <option v-for="item in graphSeriesOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
          </select>
          <select v-model="graphFilters.fault_type" class="scada-input">
            <option value="">不限故障</option>
            <option v-for="item in faultTypeOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
          </select>
          <select v-model="graphFilters.node_type" class="scada-input">
            <option value="">不限节点</option>
            <option v-for="item in nodeTypeOptions" :key="item" :value="item">{{ formatKnowledgeGraphNodeType(item) }}</option>
          </select>
          <input v-model.trim="graphFilters.keyword" class="scada-input" placeholder="关键词" />
          <button class="scada-button" type="button" @click="loadGraph">加载图谱</button>
        </div>

        <div v-if="graphData.nodes.length" class="graph-canvas">
          <svg class="graph-svg" viewBox="0 0 1000 600" preserveAspectRatio="none">
            <line
              v-for="edge in graphEdgeLines"
              :key="edge.edge.id"
              :x1="edge.source.x * 10"
              :y1="edge.source.y * 6"
              :x2="edge.target.x * 10"
              :y2="edge.target.y * 6"
              class="graph-link"
              :class="{ selected: selectedGraphEdge?.id === edge.edge.id }"
              @click="selectGraphEdge(edge.edge)"
            />
          </svg>
          <button
            v-for="position in graphNodePositions"
            :key="position.node.id"
            class="graph-node"
            :class="[`node-${position.node.node_type}`, { selected: selectedGraphNode?.id === position.node.id }]"
            type="button"
            :style="{ left: `${position.x}%`, top: `${position.y}%` }"
            @click="selectGraphNode(position.node)"
          >
            <span>{{ position.node.display_name || position.node.canonical_name }}</span>
            <small>{{ formatKnowledgeGraphNodeType(position.node.node_type) }}</small>
          </button>
        </div>
        <EmptyState v-else text="暂无可展示图谱，请先种子化或抽取并审核图谱候选。" />
      </DataPanel>

      <div class="space-y-4">
        <DataPanel title="图例">
          <div class="grid grid-cols-2 gap-2 text-xs text-slate-300">
            <span v-for="item in graphLegendItems" :key="item.key" class="rounded border border-slate-600/20 bg-black/20 px-2 py-1">
              {{ item.label }}
            </span>
          </div>
        </DataPanel>

        <DataPanel title="选中对象详情">
          <div v-if="selectedGraphNode" class="space-y-2 text-sm text-slate-300">
            <h3 class="font-black text-white">{{ selectedGraphNode.display_name || selectedGraphNode.canonical_name }}</h3>
            <p>{{ formatKnowledgeGraphNodeType(selectedGraphNode.node_type) }} / {{ labelOfManufacturer(selectedGraphNode.manufacturer) }} / {{ selectedGraphNode.product_series || '-' }}</p>
            <p>证据 {{ selectedGraphNode.evidence_count || 0 }} · 置信度 {{ formatConfidence(selectedGraphNode.confidence) }}</p>
            <button class="scada-button !min-h-8 !px-3" type="button" @click="expandSelectedGraphNode">展开邻域</button>
          </div>
          <div v-else-if="selectedGraphEdge" class="space-y-2 text-sm text-slate-300">
            <h3 class="font-black text-white">{{ formatKnowledgeGraphRelation(selectedGraphEdge.relation_type) }}</h3>
            <p>{{ selectedGraphEdge.source_node_name || selectedGraphEdge.source_node_id }} → {{ selectedGraphEdge.target_node_name || selectedGraphEdge.target_node_id }}</p>
            <p>证据 {{ selectedGraphEdge.evidence_count }} · 置信度 {{ formatConfidence(selectedGraphEdge.confidence) }}</p>
          </div>
          <EmptyState v-else text="点击节点或关系查看详情。" />
        </DataPanel>

        <DataPanel title="图谱证据">
          <div v-if="selectedEvidence.length" class="space-y-2">
            <article v-for="item in selectedEvidence" :key="item.id" class="rounded-md border border-slate-600/20 bg-black/20 p-3 text-sm text-slate-300">
              <div class="text-xs font-bold text-cyan-200">{{ item.source_type }}</div>
              <p class="mt-2 leading-6">{{ item.evidence_text || '暂无证据文本' }}</p>
              <p class="mt-2 break-all font-mono text-xs text-slate-500">{{ item.chunk_id || item.document_id || item.source_id || item.id }}</p>
            </article>
          </div>
          <EmptyState v-else text="选择带证据的节点或关系后显示 evidence。" />
        </DataPanel>
      </div>
    </section>

    <section v-if="activeTab === 'nodes'" class="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
      <DataPanel title="图谱节点">
        <div class="mb-4 grid gap-3 md:grid-cols-4">
          <select v-model="nodeFilters.node_type" class="scada-input">
            <option value="">不限类型</option>
            <option v-for="item in nodeTypeOptions" :key="item" :value="item">{{ formatKnowledgeGraphNodeType(item) }}</option>
          </select>
          <input v-model.trim="nodeFilters.keyword" class="scada-input" placeholder="搜索节点名称" />
          <select v-model="nodeFilters.status" class="scada-input">
            <option value="">不限状态</option>
            <option value="active">启用</option>
            <option value="archived">已归档</option>
          </select>
          <button class="scada-button" type="button" @click="loadNodes">查询</button>
        </div>
        <div v-if="nodes.length" class="space-y-3">
          <article v-for="node in nodes" :key="node.id" class="rounded-md border border-slate-600/20 bg-black/20 p-4">
            <div class="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
              <div class="min-w-0">
                <h3 class="break-words font-black text-white">{{ node.display_name || node.canonical_name }}</h3>
                <p class="mt-1 text-xs text-slate-400">
                  {{ formatKnowledgeGraphNodeType(node.node_type) }} / {{ labelOfManufacturer(node.manufacturer) }} / {{ node.product_series || '-' }}
                </p>
                <p class="mt-2 text-xs text-slate-500">
                  证据 {{ node.evidence_count || 0 }} · 置信度 {{ formatConfidence(node.confidence) }}
                </p>
              </div>
              <div class="flex flex-wrap items-center gap-2">
                <StatusPill :value="node.status" />
                <button class="scada-button !min-h-8 !px-3" type="button" @click="selectNeighborhood(node.id)">邻域</button>
                <button v-if="canManage" class="scada-button !min-h-8 !px-3" type="button" @click="archiveNode(node.id)">归档</button>
              </div>
            </div>
          </article>
        </div>
        <EmptyState v-else text="暂无图谱节点" />
      </DataPanel>

      <DataPanel v-if="canManage" title="新建节点">
        <div class="space-y-3">
          <select v-model="nodeForm.node_type" class="scada-input">
            <option v-for="item in nodeTypeOptions" :key="item" :value="item">{{ formatKnowledgeGraphNodeType(item) }}</option>
          </select>
          <input v-model.trim="nodeForm.canonical_name" class="scada-input" placeholder="标准名称" />
          <input v-model.trim="nodeForm.display_name" class="scada-input" placeholder="展示名称" />
          <select v-model="nodeForm.manufacturer" class="scada-input">
            <option value="">不限厂家</option>
            <option v-for="item in manufacturerOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
          </select>
          <select v-model="nodeForm.product_series" class="scada-input">
            <option value="">不限系列</option>
            <option v-for="item in productSeriesOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
          </select>
          <button class="scada-button w-full" type="button" @click="createNode">创建节点</button>
        </div>
      </DataPanel>
    </section>

    <section v-if="activeTab === 'edges'" class="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
      <DataPanel title="图谱关系">
        <div v-if="edges.length" class="space-y-3">
          <article v-for="edge in edges" :key="edge.id" class="rounded-md border border-slate-600/20 bg-black/20 p-4">
            <div class="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
              <div>
                <h3 class="font-black text-white">{{ formatKnowledgeGraphRelation(edge.relation_type) }}</h3>
                <p class="mt-1 text-sm text-slate-300">
                  {{ edge.source_node_name || edge.source_node_id }} → {{ edge.target_node_name || edge.target_node_id }}
                </p>
                <p class="mt-2 text-xs text-slate-500">
                  {{ edge.relation_type }} · 证据 {{ edge.evidence_count }} · 置信度 {{ formatConfidence(edge.confidence) }}
                </p>
              </div>
              <div class="flex flex-wrap items-center gap-2">
                <StatusPill :value="edge.status" />
                <button v-if="canManage" class="scada-button !min-h-8 !px-3" type="button" @click="archiveEdge(edge.id)">归档</button>
              </div>
            </div>
          </article>
        </div>
        <EmptyState v-else text="暂无图谱关系" />
      </DataPanel>

      <DataPanel v-if="canManage" title="新建关系">
        <div class="space-y-3">
          <select v-model="edgeForm.source_node_id" class="scada-input">
            <option value="">选择起点节点</option>
            <option v-for="node in nodes" :key="node.id" :value="node.id">{{ node.display_name || node.canonical_name }}</option>
          </select>
          <select v-model="edgeForm.target_node_id" class="scada-input">
            <option value="">选择终点节点</option>
            <option v-for="node in nodes" :key="node.id" :value="node.id">{{ node.display_name || node.canonical_name }}</option>
          </select>
          <select v-model="edgeForm.relation_type" class="scada-input">
            <option v-for="item in relationTypeOptions" :key="item" :value="item">{{ formatKnowledgeGraphRelation(item) }}</option>
          </select>
          <textarea v-model.trim="edgeForm.evidence_text" class="scada-input min-h-24" placeholder="证据摘要，可选"></textarea>
          <button class="scada-button w-full" type="button" @click="createEdge">创建关系</button>
        </div>
      </DataPanel>
    </section>

    <section v-if="activeTab === 'candidates'" class="grid gap-4 xl:grid-cols-[360px_minmax(0,1fr)]">
      <DataPanel title="规则抽取">
        <div class="space-y-3">
          <select v-model="selectedDocumentId" class="scada-input">
            <option value="">选择已批准知识文档</option>
            <option v-for="doc in documents" :key="doc.id" :value="doc.id">{{ doc.title }}</option>
          </select>
          <button v-if="canManage" class="scada-button w-full" type="button" :disabled="!selectedDocumentId" @click="extractFromDocument">
            从文档抽取候选
          </button>
          <p v-else class="text-xs leading-6 text-slate-400">当前账号仅可查看图谱，候选抽取和审核需要专家或管理员权限。</p>
        </div>
      </DataPanel>

      <DataPanel title="待审核候选">
        <div v-if="candidates.length" class="space-y-3">
          <article v-for="candidate in candidates" :key="candidate.id" class="rounded-md border border-slate-600/20 bg-black/20 p-4">
            <div class="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
              <div class="min-w-0">
                <h3 class="font-black text-white">{{ candidateTitle(candidate) }}</h3>
                <p class="mt-1 text-xs text-slate-400">
                  {{ candidate.candidate_type }} · {{ formatStatusLabel(candidate.status) }} · 置信度 {{ formatConfidence(candidate.confidence) }}
                </p>
                <p class="mt-2 line-clamp-2 text-sm text-slate-300">{{ candidate.evidence_text || '暂无证据摘要' }}</p>
              </div>
              <div class="flex flex-wrap items-center gap-2">
                <StatusPill :value="candidate.status" />
                <button v-if="canManage && candidate.status === 'pending'" class="scada-button !min-h-8 !px-3" type="button" @click="approveCandidate(candidate.id)">通过</button>
                <button v-if="canManage && candidate.status === 'pending'" class="scada-button !min-h-8 !px-3" type="button" @click="rejectCandidate(candidate.id)">驳回</button>
              </div>
            </div>
          </article>
        </div>
        <EmptyState v-else text="暂无图谱候选" />
      </DataPanel>
    </section>

    <section v-if="activeTab === 'runs'" class="grid gap-4 lg:grid-cols-2">
      <DataPanel title="抽取运行">
        <div v-if="runs.length" class="space-y-3">
          <article v-for="run in runs" :key="run.id" class="rounded-md border border-slate-600/20 bg-black/20 p-4">
            <div class="flex items-start justify-between gap-3">
              <div>
                <h3 class="font-black text-white">{{ run.source_type }}</h3>
                <p class="mt-1 text-xs text-slate-400">{{ run.extractor }} · 候选 {{ run.candidate_count }}</p>
                <p class="mt-2 text-xs text-slate-500">{{ formatTime(run.created_at) }}</p>
              </div>
              <StatusPill :value="run.status" />
            </div>
          </article>
        </div>
        <EmptyState v-else text="暂无抽取运行" />
      </DataPanel>

      <DataPanel title="证据链接">
        <div v-if="evidenceList.length" class="space-y-3">
          <article v-for="item in evidenceList" :key="item.id" class="rounded-md border border-slate-600/20 bg-black/20 p-4">
            <div class="text-xs font-bold text-slate-400">{{ item.source_type }}</div>
            <p class="mt-2 text-sm leading-6 text-slate-200">{{ item.evidence_text || '暂无证据文本' }}</p>
            <p class="mt-2 font-mono text-xs text-slate-500">{{ item.chunk_id || item.document_id || item.source_id }}</p>
          </article>
        </div>
        <EmptyState v-else text="暂无证据链接" />
      </DataPanel>
    </section>

    <section v-if="activeTab === 'neighborhood'" class="grid gap-4 lg:grid-cols-[360px_minmax(0,1fr)]">
      <DataPanel title="邻域查询">
        <div class="space-y-3">
          <select v-model="selectedNodeId" class="scada-input">
            <option value="">选择中心节点</option>
            <option v-for="node in nodes" :key="node.id" :value="node.id">{{ node.display_name || node.canonical_name }}</option>
          </select>
          <button class="scada-button w-full" type="button" :disabled="!selectedNodeId" @click="loadNeighborhood">查询邻域</button>
        </div>
      </DataPanel>
      <DataPanel title="邻域结果">
        <div v-if="neighborhood" class="space-y-4">
          <div>
            <div class="text-xs font-bold text-slate-400">中心节点</div>
            <div class="mt-1 font-black text-white">{{ neighborhood.center.display_name || neighborhood.center.canonical_name }}</div>
          </div>
          <div>
            <div class="text-xs font-bold text-slate-400">相关节点</div>
            <div class="mt-2 flex flex-wrap gap-2">
              <span v-for="node in neighborhood.nodes" :key="node.id" class="rounded border border-slate-600/30 px-2 py-1 text-xs text-slate-200">
                {{ node.display_name || node.canonical_name }}
              </span>
            </div>
          </div>
          <div>
            <div class="text-xs font-bold text-slate-400">相关关系</div>
            <div class="mt-2 space-y-2">
              <p v-for="edge in neighborhood.edges" :key="edge.id" class="text-xs text-slate-300">
                {{ edge.source_node_name }} → {{ formatKnowledgeGraphRelation(edge.relation_type) }} → {{ edge.target_node_name }}
              </p>
            </div>
          </div>
        </div>
        <EmptyState v-else text="请选择节点查看邻域" />
      </DataPanel>
    </section>

    <section v-if="activeTab === 'path'" class="grid gap-4 lg:grid-cols-[360px_minmax(0,1fr)]">
      <DataPanel title="路径查询">
        <div class="space-y-3">
          <select v-model="pathForm.source_node_id" class="scada-input">
            <option value="">选择起点节点</option>
            <option v-for="node in nodes" :key="node.id" :value="node.id">{{ node.display_name || node.canonical_name }}</option>
          </select>
          <select v-model="pathForm.target_node_id" class="scada-input">
            <option value="">选择终点节点</option>
            <option v-for="node in nodes" :key="node.id" :value="node.id">{{ node.display_name || node.canonical_name }}</option>
          </select>
          <select v-model.number="pathForm.max_depth" class="scada-input">
            <option :value="2">2 跳</option>
            <option :value="3">3 跳</option>
            <option :value="4">4 跳</option>
            <option :value="5">5 跳</option>
          </select>
          <button class="scada-button w-full" type="button" :disabled="!pathForm.source_node_id || !pathForm.target_node_id" @click="loadPath">
            查询路径
          </button>
        </div>
      </DataPanel>
      <DataPanel title="路径结果">
        <div v-if="pathResult?.found" class="space-y-4">
          <div class="flex flex-wrap gap-2">
            <span v-for="node in pathResult.nodes" :key="node.id" class="rounded border border-cyan-300/20 bg-cyan-400/10 px-2 py-1 text-xs text-cyan-100">
              {{ node.display_name || node.canonical_name }}
            </span>
          </div>
          <div class="space-y-2">
            <p v-for="edge in pathResult.edges" :key="edge.id" class="text-sm text-slate-300">
              {{ edge.source_node_name }} → {{ formatKnowledgeGraphRelation(edge.relation_type) }} → {{ edge.target_node_name }}
            </p>
          </div>
        </div>
        <EmptyState v-else :text="pathResult ? '未找到指定深度内的 active 图谱路径。' : '请选择起点和终点查询路径。'" />
      </DataPanel>
    </section>
  </PageFrame>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { RefreshCcw } from '@lucide/vue'
import {
  approveKnowledgeGraphCandidateApi,
  bootstrapKnowledgeGraphApi,
  archiveKnowledgeGraphEdgeApi,
  archiveKnowledgeGraphNodeApi,
  createKnowledgeGraphEdgeApi,
  createKnowledgeGraphNodeApi,
  extractKnowledgeGraphFromDocumentApi,
  getDocumentsApi,
  getKnowledgeGraphGraphApi,
  getKnowledgeGraphCandidatesApi,
  getKnowledgeGraphEdgesApi,
  getKnowledgeGraphEvidenceApi,
  getKnowledgeGraphExtractionRunsApi,
  getKnowledgeGraphNeighborhoodApi,
  getKnowledgeGraphNodesApi,
  getKnowledgeGraphPathApi,
  getKnowledgeGraphOverviewApi,
  rejectKnowledgeGraphCandidateApi
} from '@/api'
import DataPanel from '@/components/DataPanel.vue'
import EmptyState from '@/components/EmptyState.vue'
import PageFrame from '@/components/PageFrame.vue'
import StatusPill from '@/components/StatusPill.vue'
import { useUserStore } from '@/stores/user'
import type { KGEdge, KGEvidence, KGExtractionRun, KGGraphEdge, KGGraphResponse, KGNeighborhood, KGNode, KGOverview, KGPathResponse, KGCandidate, KnowledgeDocument } from '@/types'
import { faultTypeOptions, manufacturerOptions, productSeriesOptions } from '@/types'
import {
  formatKnowledgeGraphNodeType,
  formatKnowledgeGraphRelation,
  formatStatusLabel
} from '@/utils/display'

const userStore = useUserStore()
const loading = ref(false)
const initializing = ref(false)
const error = ref('')
const activeTab = ref('overview')
const overview = ref<KGOverview | null>(null)
const nodes = ref<KGNode[]>([])
const edges = ref<KGEdge[]>([])
const candidates = ref<KGCandidate[]>([])
const runs = ref<KGExtractionRun[]>([])
const evidenceList = ref<KGEvidence[]>([])
const documents = ref<KnowledgeDocument[]>([])
const graphData = ref<KGGraphResponse>({ nodes: [], edges: [], statistics: {}, legend: {} })
const selectedGraphNode = ref<KGNode | null>(null)
const selectedGraphEdge = ref<KGGraphEdge | null>(null)
const selectedEvidence = ref<KGEvidence[]>([])
const pathResult = ref<KGPathResponse | null>(null)
const selectedDocumentId = ref('')
const selectedNodeId = ref('')
const neighborhood = ref<KGNeighborhood | null>(null)

const tabs = [
  { key: 'overview', label: '总览' },
  { key: 'graph', label: '图谱视图' },
  { key: 'nodes', label: '节点' },
  { key: 'edges', label: '关系' },
  { key: 'candidates', label: '候选审核' },
  { key: 'runs', label: '运行与证据' },
  { key: 'neighborhood', label: '邻域' },
  { key: 'path', label: '路径查询' }
]

const nodeTypeOptions = [
  'manufacturer',
  'product_series',
  'device_model',
  'fault',
  'alarm',
  'component',
  'symptom',
  'cause',
  'inspection_item',
  'action',
  'tool',
  'part',
  'safety_risk',
  'knowledge_document',
  'knowledge_chunk',
  'contribution'
]

const relationTypeOptions = [
  'BELONGS_TO',
  'HAS_FAULT',
  'HAS_ALARM',
  'HAS_SYMPTOM',
  'CAUSED_BY',
  'CHECK_BY',
  'RESOLVED_BY',
  'USES_TOOL',
  'REQUIRES_PART',
  'HAS_SAFETY_RISK',
  'MENTIONED_IN',
  'DERIVED_FROM',
  'RELATED_TO'
]

const nodeFilters = reactive({ node_type: '', keyword: '', status: '' })
const graphFilters = reactive({
  manufacturer: '',
  product_series: '',
  fault_type: '',
  node_type: '',
  relation_type: '',
  keyword: '',
  depth: 1,
  limit: 80
})
const nodeForm = reactive({
  node_type: 'fault',
  canonical_name: '',
  display_name: '',
  manufacturer: '',
  product_series: '',
  device_type: 'pv_inverter'
})
const edgeForm = reactive({
  source_node_id: '',
  target_node_id: '',
  relation_type: 'RELATED_TO',
  evidence_text: ''
})
const pathForm = reactive({
  source_node_id: '',
  target_node_id: '',
  max_depth: 3
})

const canManage = computed(() => ['admin', 'expert'].includes(userStore.role || ''))
const graphSeriesOptions = computed(() => productSeriesOptions.filter((item) => !graphFilters.manufacturer || item.manufacturer === graphFilters.manufacturer))
const overviewCards = computed(() => [
  { label: '节点数', value: overview.value?.node_count ?? 0, detail: 'kg_nodes' },
  { label: '关系数', value: overview.value?.edge_count ?? 0, detail: 'kg_edges' },
  { label: '证据数', value: overview.value?.evidence_count ?? 0, detail: 'kg_evidence_links' },
  { label: '待审候选', value: overview.value?.pending_candidate_count ?? 0, detail: 'kg_candidates' },
  { label: '完成抽取', value: overview.value?.completed_run_count ?? 0, detail: 'kg_extraction_runs' }
])
const nodeTypeItems = computed(() => toEntries(overview.value?.node_type_counts))
const relationTypeItems = computed(() => toEntries(overview.value?.relation_type_counts))
const graphLegendItems = computed(() => {
  const nodeLegend = (graphData.value.legend?.node_types || {}) as Record<string, string>
  return Object.entries(nodeLegend).map(([key, label]) => ({ key, label }))
})
const graphNodePositions = computed(() => {
  const layerByType: Record<string, number> = {
    manufacturer: 0, product_series: 0,
    device_model: 1, fault: 1, alarm: 1,
    symptom: 2, cause: 2, component: 2, inspection_item: 2,
    action: 3, tool: 3, part: 3, safety_risk: 3, sop_template: 3
  }
  const layers = new Map<number, KGNode[]>()
  for (const node of graphData.value.nodes || []) {
    const layer = layerByType[node.node_type] ?? 2
    layers.set(layer, [...(layers.get(layer) || []), node])
  }
  return [...layers.entries()].flatMap(([layer, items]) =>
    items.map((node, index) => ({
      node,
      x: ((index + 1) / (items.length + 1)) * 84 + 8,
      y: 12 + layer * 25
    }))
  )
})
const graphPositionMap = computed(() => new Map(graphNodePositions.value.map((item) => [item.node.id, item])))
const graphEdgeLines = computed(() =>
  (graphData.value.edges || [])
    .map((edge) => {
      const source = graphPositionMap.value.get(edge.source_node_id)
      const target = graphPositionMap.value.get(edge.target_node_id)
      return source && target ? { edge, source, target } : null
    })
    .filter(Boolean) as Array<{ edge: KGGraphEdge; source: { x: number; y: number }; target: { x: number; y: number } }>
)

async function loadAll() {
  loading.value = true
  error.value = ''
  try {
    await Promise.all([loadOverview(), loadGraph(), loadNodes(), loadEdges(), loadCandidates(), loadRuns(), loadEvidence(), loadDocuments()])
  } catch (err) {
    error.value = err instanceof Error ? err.message : '知识图谱数据读取失败'
  } finally {
    loading.value = false
  }
}

async function loadOverview() {
  overview.value = await getKnowledgeGraphOverviewApi()
}

async function loadNodes() {
  const params: Record<string, string | number> = { page: 1, page_size: 50 }
  if (nodeFilters.node_type) params.node_type = nodeFilters.node_type
  if (nodeFilters.keyword) params.keyword = nodeFilters.keyword
  if (nodeFilters.status) params.status = nodeFilters.status
  const result = await getKnowledgeGraphNodesApi(params)
  nodes.value = result.items
}

async function loadGraph() {
  const params: Record<string, string | number> = { limit: graphFilters.limit, depth: graphFilters.depth }
  if (graphFilters.manufacturer) params.manufacturer = graphFilters.manufacturer
  if (graphFilters.product_series) params.product_series = graphFilters.product_series
  if (graphFilters.fault_type) params.fault_type = graphFilters.fault_type
  if (graphFilters.node_type) params.node_type = graphFilters.node_type
  if (graphFilters.relation_type) params.relation_type = graphFilters.relation_type
  if (graphFilters.keyword) params.keyword = graphFilters.keyword
  graphData.value = await getKnowledgeGraphGraphApi(params)
  selectedGraphNode.value = null
  selectedGraphEdge.value = null
  selectedEvidence.value = []
}

async function bootstrapGraph() {
  initializing.value = true
  await action(async () => {
    await bootstrapKnowledgeGraphApi({ max_documents: 6, max_chunks_per_document: 40 })
    await Promise.all([loadOverview(), loadGraph(), loadNodes(), loadEdges(), loadCandidates(), loadRuns(), loadEvidence()])
    activeTab.value = 'graph'
  }, '图谱初始化完成')
  initializing.value = false
}

async function loadEdges() {
  const result = await getKnowledgeGraphEdgesApi({ page: 1, page_size: 50 })
  edges.value = result.items
}

async function loadCandidates() {
  const result = await getKnowledgeGraphCandidatesApi({ status: 'pending', page: 1, page_size: 50 })
  candidates.value = result.items
}

async function loadRuns() {
  const result = await getKnowledgeGraphExtractionRunsApi({ page: 1, page_size: 20 })
  runs.value = result.items
}

async function loadEvidence() {
  const result = await getKnowledgeGraphEvidenceApi({ page: 1, page_size: 20 })
  evidenceList.value = result.items
}

async function loadDocuments() {
  const result = await getDocumentsApi({ parse_status: 'parsed', review_status: 'approved', page: 1, page_size: 50 })
  documents.value = result.items
}

async function createNode() {
  if (!nodeForm.canonical_name.trim()) return
  await action(async () => {
    await createKnowledgeGraphNodeApi({
      node_type: nodeForm.node_type,
      canonical_name: nodeForm.canonical_name,
      display_name: nodeForm.display_name || nodeForm.canonical_name,
      manufacturer: nodeForm.manufacturer || null,
      product_series: nodeForm.product_series || null,
      device_type: nodeForm.device_type,
      aliases: nodeForm.display_name ? [nodeForm.display_name] : []
    })
    nodeForm.canonical_name = ''
    nodeForm.display_name = ''
    await Promise.all([loadOverview(), loadNodes()])
  }, '节点已创建')
}

async function createEdge() {
  if (!edgeForm.source_node_id || !edgeForm.target_node_id) return
  await action(async () => {
    await createKnowledgeGraphEdgeApi({
      source_node_id: edgeForm.source_node_id,
      target_node_id: edgeForm.target_node_id,
      relation_type: edgeForm.relation_type,
      display_relation: formatKnowledgeGraphRelation(edgeForm.relation_type),
      evidence_text: edgeForm.evidence_text || null
    })
    edgeForm.evidence_text = ''
    await Promise.all([loadOverview(), loadEdges(), loadEvidence()])
  }, '关系已创建')
}

async function archiveNode(nodeId: string) {
  await action(async () => {
    await archiveKnowledgeGraphNodeApi(nodeId)
    await Promise.all([loadOverview(), loadNodes()])
  }, '节点已归档')
}

async function archiveEdge(edgeId: string) {
  await action(async () => {
    await archiveKnowledgeGraphEdgeApi(edgeId)
    await Promise.all([loadOverview(), loadEdges()])
  }, '关系已归档')
}

async function extractFromDocument() {
  if (!selectedDocumentId.value) return
  await action(async () => {
    await extractKnowledgeGraphFromDocumentApi(selectedDocumentId.value, { max_chunks: 80 })
    await Promise.all([loadOverview(), loadCandidates(), loadRuns()])
  }, '抽取候选已生成')
}

async function approveCandidate(candidateId: string) {
  await action(async () => {
    await approveKnowledgeGraphCandidateApi(candidateId, '前端审核通过')
    await Promise.all([loadOverview(), loadNodes(), loadEdges(), loadCandidates(), loadEvidence()])
  }, '候选已通过')
}

async function rejectCandidate(candidateId: string) {
  await action(async () => {
    await rejectKnowledgeGraphCandidateApi(candidateId, '前端审核驳回')
    await Promise.all([loadOverview(), loadCandidates()])
  }, '候选已驳回')
}

function selectNeighborhood(nodeId: string) {
  selectedNodeId.value = nodeId
  activeTab.value = 'neighborhood'
  void loadNeighborhood()
}

async function selectGraphNode(node: KGNode) {
  selectedGraphNode.value = node
  selectedGraphEdge.value = null
  const result = await getKnowledgeGraphEvidenceApi({ node_id: node.id, page: 1, page_size: 10 })
  selectedEvidence.value = result.items
}

async function selectGraphEdge(edge: KGGraphEdge) {
  selectedGraphEdge.value = edge
  selectedGraphNode.value = null
  const result = await getKnowledgeGraphEvidenceApi({ edge_id: edge.id, page: 1, page_size: 10 })
  selectedEvidence.value = result.items
}

async function expandSelectedGraphNode() {
  if (!selectedGraphNode.value) return
  const result = await getKnowledgeGraphNeighborhoodApi(selectedGraphNode.value.id, { depth: 2 })
  graphData.value = {
    nodes: result.nodes,
    edges: result.edges,
    statistics: { node_count: result.nodes.length, edge_count: result.edges.length, source: 'neighborhood' },
    legend: graphData.value.legend
  }
}

async function loadNeighborhood() {
  if (!selectedNodeId.value) return
  neighborhood.value = await getKnowledgeGraphNeighborhoodApi(selectedNodeId.value, { depth: 1 })
}

async function loadPath() {
  if (!pathForm.source_node_id || !pathForm.target_node_id) return
  pathResult.value = await getKnowledgeGraphPathApi({
    source_node_id: pathForm.source_node_id,
    target_node_id: pathForm.target_node_id,
    max_depth: pathForm.max_depth
  })
}

async function action(fn: () => Promise<void>, message: string) {
  error.value = ''
  try {
    await fn()
    window.dispatchEvent(new CustomEvent('app:toast', { detail: { message } }))
  } catch (err) {
    error.value = err instanceof Error ? err.message : '知识图谱操作失败'
  }
}

function candidateTitle(candidate: KGCandidate) {
  const payload = candidate.payload_json || {}
  if (candidate.candidate_type === 'node') {
    return `${formatKnowledgeGraphNodeType(String(payload.node_type || ''))}：${payload.display_name || payload.canonical_name || candidate.id}`
  }
  if (candidate.candidate_type === 'edge') {
    const source = (payload.source_node || {}) as Record<string, unknown>
    const target = (payload.target_node || {}) as Record<string, unknown>
    return `${source.display_name || source.canonical_name || '节点'} → ${formatKnowledgeGraphRelation(String(payload.relation_type || ''))} → ${target.display_name || target.canonical_name || '节点'}`
  }
  return `别名候选：${candidate.id}`
}

function labelOfManufacturer(value?: string | null) {
  return manufacturerOptions.find((item) => item.value === value)?.label ?? value ?? '-'
}

function formatConfidence(value?: number | null) {
  return value == null ? '-' : `${Math.round(value * 100)}%`
}

function formatTime(value?: string | null) {
  return value ? new Date(value).toLocaleString('zh-CN') : '-'
}

function toEntries(value?: Record<string, number>) {
  return Object.entries(value || {}).map(([key, itemValue]) => ({ key, value: itemValue }))
}

onMounted(loadAll)
</script>

<style scoped>
.graph-canvas {
  position: relative;
  min-height: 560px;
  overflow: hidden;
  border: 1px solid rgb(71 85 105 / 0.28);
  border-radius: 8px;
  background:
    linear-gradient(90deg, rgb(148 163 184 / 0.05) 1px, transparent 1px),
    linear-gradient(rgb(148 163 184 / 0.05) 1px, transparent 1px),
    rgb(2 6 23 / 0.42);
  background-size: 28px 28px;
}

.graph-svg {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}

.graph-link {
  cursor: pointer;
  stroke: rgb(125 211 252 / 0.38);
  stroke-width: 2;
}

.graph-link:hover,
.graph-link.selected {
  stroke: rgb(103 232 249 / 0.9);
  stroke-width: 4;
}

.graph-node {
  position: absolute;
  display: grid;
  min-width: 112px;
  max-width: 150px;
  transform: translate(-50%, -50%);
  gap: 2px;
  border: 1px solid rgb(103 232 249 / 0.35);
  border-radius: 8px;
  background: rgb(15 23 42 / 0.88);
  padding: 8px 10px;
  text-align: left;
  color: #e2e8f0;
  box-shadow: 0 12px 30px rgb(0 0 0 / 0.26);
}

.graph-node span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
  font-weight: 800;
}

.graph-node small {
  color: #94a3b8;
  font-size: 10px;
}

.graph-node:hover,
.graph-node.selected {
  border-color: rgb(103 232 249 / 0.9);
  background: rgb(8 47 73 / 0.92);
}

.node-fault,
.node-alarm {
  border-color: rgb(251 191 36 / 0.45);
}

.node-cause,
.node-safety_risk {
  border-color: rgb(248 113 113 / 0.48);
}

.node-action,
.node-inspection_item,
.node-tool,
.node-part {
  border-color: rgb(52 211 153 / 0.48);
}
</style>
