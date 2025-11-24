import mermaid as md
from mermaid.graph import Graph

render = md.Mermaid("""
graph TD
    subgraph "Setup Inicial"
        A[Início do Script: `if __name__ == '__main__'`] --> B[Definir Parâmetros da Simulação];
        B --> C[Definir Parâmetros da Frota e Depósito];
        C --> D[Criar Cronograma de Chegada dos Pedidos];
        D --> E[Instanciar o `System`];
        E --> F[Chamar `system.run_simulation()`];

        subgraph "Parâmetros da Simulação"
            B1[Start Time]
            B2[End Time]
            B3[Fuso Horário (TZ)]
            B4[Hiperparâmetros JIT: Buffer, Limite de Fila, etc.]
        end

        subgraph "Frota e Depósito"
            C1[Criar Objetos `Vehicle` com suas capacidades]
            C2[Definir localização do `Depot`]
        end
    end
""")

render.save
