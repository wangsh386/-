# 这是在基于Qt5 以及边缘检测，圆形/矩形拟合的可视化的检测工件尺寸程序

# Industrial Workpiece Dimension Measurement System

![Application Screenshot](output.png)

A Qt5-based visualization program for edge detection and geometric shape fitting, designed for precise dimensional measurement of industrial workpieces with camera/image input support.

## Features
- 🎥 **Multi-source input**: USB camera live capture & local image processing
- 🔍 **Precision detection**: 
  - Zernike moment sub-pixel edge detection
  - Hough circle transform + contour approximation
- 📏 **Dimension measurement**:
  - Circle diameter calculation
  - Rectangle width/height measurement
  - Pixel-to-real conversion with calibration
- 🖥️ **Interactive UI**: Real-time visualization pipeline

## System Diagram
```mermaid
graph LR
    A[Input] --> B(Preprocessing)
    B --> C[Edge Detection]
    C --> D{Shape Detection}
    D -->|Circle| E[Hough Transform]
    D -->|Rectangle| F[Contour Analysis]
    E & F --> G[Dimension Calculation]
    G --> H[Visualization]

graph LR
    subgraph 输入特征
        A[图结构特征 Hg] --> B[投影层]
        C[SMILES特征 Hs] --> D[投影层]
        E[几何特征 Hh] --> F[投影层]
    end
    
    subgraph 交叉注意力计算
        B -->|Q_G| G[G→S Attn]
        D -->|K_S, V_S| G
        B -->|Q_G| H[G→H Attn]
        F -->|K_H, V_H| H
        
        D -->|Q_S| I[S→G Attn]
        B -->|K_G, V_G| I
        D -->|Q_S| J[S→H Attn]
        F -->|K_H, V_H| J
        
        F -->|Q_H| K[H→G Attn]
        B -->|K_G, V_G| K
        F -->|Q_H| L[H→S Attn]
        D -->|K_S, V_S| L
    end
    
    subgraph 特征融合
        G & H --> M[Hg_new = Hg + ΣAttn]
        I & J --> N[Hs_new = Hs + ΣAttn]
        K & L --> O[Hh_new = Hh + ΣAttn]
        M & N & O --> P[加权融合]
    end
    
    P --> Q[最终表示 H_final]
