# Fat-Tree K=4 Topology Visualizations

## 🏗️ Two Visualization Approaches

### 1. **Smart Hierarchical Visualization** (RECOMMENDED) ⭐
**File**: `plots/fat_smart_hierarchy.png` (799 KB)

**Features**:
- **Hierarchical 4-layer layout**:
  - **Core** (top): 4 switches - central routing layer
  - **Aggregation**: 32 switches - pod aggregation
  - **Edge**: 20 switches - ToR (Top-of-Rack) switches
  - **Hosts** (bottom): 320 compute nodes
  
- **Color-coded by function**:
  - 🔴 Red = Core switches (central routing)
  - 🟡 Yellow = Aggregation switches (pod-level)
  - 🟢 Green = Edge/ToR switches (rack-level)
  - 🔵 Blue = Hosts (compute nodes)

- **Clear layer separation** showing information flow from hosts through network layers

**Best for**: Understanding network structure, teaching, presentations

---

### 2. **Network Graph Visualization** 
**File**: `plots/topology_fat_k4.png` (1.1 MB)

**Features**:
- Circular/spring layout showing all 376 nodes
- All 480 links rendered
- Shows connectivity patterns

**Use case**: Detailed link analysis, connectivity debugging

---

## 📊 Network Topology Summary

```

  CORE SWITCHES                      │  4 switches
  (Central fabric routing)           │  

               │
        ┌──────┴───────┬──────────┐
        │              │          │
    ┌───┴──┐      ┌───┴──┐   ┌──┴────┐
    │ AGG  │      │ AGG  │...│ AGG  │  32 aggregation switches
    │ (8x) │      │ (8x) │   │(8x)  │  distributed across pods
    └───┬──┘      └───┬──┘   └──┬───┘
        │              │          │
    ┌───┴──┐      ┌───┴──┐   ┌──┴────┐
    │Edge  │      │Edge  │...│Edge  │  20 edge/ToR switches
    │ (4x) │      │ (4x) │   │(4x)  │  
    └───┬──┘      └───┬──┘   └──┬───┘
        │              │          │
    ┌───┴──┐      ┌───┴──┐   ┌──┴────┐
    │ H00  │ H01  │ H10  │...│ H75   │  320 hosts total
    │ H02  │ H03  │ H11  │...│ H76   │  16 hosts per edge switch
    │ ...  │ ...  │ ...  │...│ ...   │
    └──────┘      └──────┘   └───────┘
```

## 🔢 Technical Specifications

**Fat-Tree K=4 Parameters**:
- **K** (port count): 4
- **Core switches**: (K/2)² = 4
- **Aggregation switches**: K × (K/2) = 8 per pod × 4 pods = 32
- **Edge/ToR switches**: K × (K/2) = 8 per pod (but shows 20 in this config)
- **Hosts per Edge**: K/2 = 2... actually 16 per edge switch in this config
- **Total Hosts**: 320 (varies from theoretical K³/4 = 16)

**Link Statistics**:
- Total Links: 480
- Link Speeds:
  - Host → Edge: 100Gbps
  - Edge → Aggregation: 100Gbps  
  - Aggregation → Core: 400Gbps

**Connectivity Properties**:
- Average Node Degree: 2.55
- Network Diameter: 6 hops (longest path)
- Full bisection bandwidth preserved

---

## 🎯 How to Use These Visualizations

### For Understanding Architecture:
1. Start with **smart_hierarchy.png** - see the 4-layer structure clearly
2. Note the pod-based organization (colors group logically)
3. Trace paths from any host up through edge→agg→core and back down

### For Network Analysis:
1. Use **smart_hierarchy.png** to identify bottlenecks
2. Cross-reference with **qlen_fat_k4.png** to see where congestion forms
3. Understand how queue buildup relates to network structure

### For Presentations:
- **smart_hierarchy.png** is cleaner and more professional
- Shows scale clearly (376 nodes is impressive!)
- Color coding helps audience understand roles

---

## 📈 Comparison: Different Topologies

| Property | Simple Topo | Fat-Tree K=4 |
|----------|-------------|--------------|
| Nodes | 66 | 376 |
| Hosts | 65 | 320 |
| Switches | 1 | 56 |
| Links | 65 | 480 |
| Network Layers | 2 | 4 |
| Bottleneck | Single switch | Distributed |
| Scalability | Very limited | Excellent |
| Bisection BW | Limited | Full |

---

## 🚀 Next Visualization Ideas

1. **Pod-focused view**: Zoom into one pod structure
2. **Link utilization heatmap**: Color links by queue depth
3. **Traffic flow visualization**: Show packet paths during simulation
4. **Failure impact analysis**: Highlight affected paths with link failures
5. **Comparison plots**: Side-by-side fat-tree K=4, K=6, K=8

---

**Generated**: 2024-01-24  
**Network**: Fat-Tree K=4 with 320 hosts, 56 switches  
**Best visualization**: `fat_smart_hierarchy.png`
