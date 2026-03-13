# Architecture

This document describes the flow and design for a recursive intelligent synthesis system. The goal is to map the divergence between reality and the simulated world model to create market predictions.

```mermaid
graph TD
  A[Initial Configuration: tickers.txt] ->|formulation.json| INGEST
  subgraph INGEST [Parallel Ingestion Layer]
    B1(Supply Agents)
    B2(Logistics Agents)
    B3(Energy Agents)
  end
  
  INGEST -->|Generates isolated signal_reports| C(Corroboration Agent)
  C -->|raw_truth| FUSION(Evidence Fusion Agent)
  FUSION -->|deduplicated_signals| C_py[Python Kalman Filter Engine]
  C_py -->|mathematically_smoothed_vectors| D(Temporal Regime Interpreter)
  
  D -->|Update Node States| E[(World State Store\nworld_state.json)]
  
   E -->|Graph State| GCIG(AI Global Constraint Index Generator)
    GCIG -->|Macro Constraint Warning Signal| G(Market Director Agent)
    
    E -->|Graph State| H_py[Python Time-Series Bounds Checker]
    H_py -->|mathematical_constraint_breach| H(Constraint Breach Hypothesis Generator)
    
    E -->|Graph State| I_py[Python Monte Carlo DAG Simulator]
    I_py -->|computed_numerical_trajectory| I(Trajectory Semantic Interpreter)
    
    G -->|market_directives| J(Market Analyst Agent)
    J -->|Provides P_market_expectation| F_py[Python KL Divergence Engine]
    F_py -->|numerical_alpha_score| F(AI Alpha Divergence Semantic Interpreter)
    
    J -.->|Reflexive Market Feedback| E
    
    F -->|alpha_signal| K(Dynamic Topology Optimizer)
    H -.->|constraint_violation_alpha| K
    I -.->|predicted_consequence_alpha| 
    
    K -->|Generates new generation of| A
    K -.->|Mutates Graph Structure| E
```
