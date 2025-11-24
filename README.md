# Documentação Técnica do Módulo de Serviço

## 1. Visão Geral do Projeto

Este projeto implementa um sistema de simulação para otimização de rotas de entrega em tempo real, projetado para resolver o Problema de Roteamento de Entregas de Refeições em Tempo Real (do inglês, *Real-Time Meal Delivery Routing Problem* - RTMRDP). O núcleo do sistema, localizado no diretório `service`, é responsável por receber pedidos de entrega, agrupá-los (clusterização), definir as melhores rotas para uma frota de veículos (roteirização) e simular o processo de despacho e entrega.

O objetivo principal é minimizar os custos operacionais, que são representados por uma combinação de tempo total de rota e penalidades por atraso na entrega. O sistema é flexível, permitindo a seleção de diferentes algoritmos de clusterização e roteirização através de um arquivo de configuração, facilitando a comparação de estratégias.

## 2. Arquitetura e Componentes

A arquitetura do módulo `service` é modular e baseada em estratégias (Strategy Pattern), o que permite trocar os algoritmos de otimização facilmente. A interação entre os componentes é orquestrada pela classe `System`, que gerencia o tempo da simulação, os eventos e o estado dos pedidos e veículos.

### Diagrama de Componentes

```mermaid
graph TD
    A[System] --> B{Event Loop};
    A --> C{Routing Logic};
    C --> D[Strategy Factory];
    D --> E{Clustering Strategy};
    D --> F{Routing Strategy};
    E --> E1[CKMeansClustering];
    E --> E2[GreedyClustering];
    F --> F1[BRKGARouting];
    F --> F2[GreedyRouting];
    E1 --> G[ckmeans.py];
    E2 --> H[greedy_clustering.py];
    F1 --> I[brkga.py];
    F2 --> J[greedy_routing.py];
    A --> K[Monitor];
    A --> L[Data Structures];

    subgraph "Algoritmos"
        G; H; I; J;
    end

    subgraph "Configuração e Estratégias"
        D; E; F; E1; E2; F1; F2;
    end

    subgraph "Core"
        A; B; C; K; L;
    end
```

### Principais Módulos

-   **`system.py`**: O coração do simulador. A classe `System` gerencia a fila de eventos (usando `heapq`), o tempo da simulação, o estado dos pedidos e veículos. Ela orquestra a lógica de roteirização, chamando as estratégias de clusterização e roteirização em intervalos definidos.
-   **`strategies.py`**: Define as interfaces abstratas (`ClusteringStrategy`, `RoutingStrategy`) e implementa as classes concretas que encapsulam os diferentes algoritmos. Por exemplo, `CKMeansClustering` e `BRKGARouting`.
-   **`factory.py`**: Implementa a função `get_strategies`, que atua como uma fábrica para criar e retornar as instâncias das estratégias corretas com base na configuração da simulação (`SimulationConfig`).
-   **`config.py`**: Centraliza as configurações da simulação. Define `Enums` para os algoritmos disponíveis (`ClusteringAlgorithm`, `RoutingAlgorithm`) e um `dataclass` (`SimulationConfig`) para manter a configuração atual.
-   **`structures.py`**: Contém as estruturas de dados fundamentais do projeto, como `Delivery`, `Vehicle`, `Point` e `Event`, definidas como `dataclasses` para clareza e robustez.
-   **`helpers.py`**: Fornece funções utilitárias, principalmente `evaluate_sequence`, que é a função de avaliação (fitness) usada pelos algoritmos de roteirização para calcular a qualidade de uma rota (penalidades e tempo). Também contém funções para conversão entre `datetime` e minutos.
-   **`distances.py`**: Funções para calcular matrizes de distância e tempo entre pontos geográficos, abstraindo os cálculos de geometria.
-   **`monitor.py`**: Uma classe `dataclass` simples para coletar e exibir métricas de desempenho da simulação, como total de entregas, penalidades e tempo em rota.
-   **Algoritmos**:
    -   `clustering/ckmeans.py`: Implementa o K-Means com restrição de capacidade, usando programação inteira mista (MIP) para a etapa de atribuição.
    -   `heuristics/greedy_clustering.py`: Uma heurística gulosa que ordena as entregas por distância e as atribui sequencialmente aos veículos.
    -   `metaheuristics/brkga.py`: Implementa a meta-heurística BRKGA (Biased Random-Key Genetic Algorithm) para resolver o problema de roteirização, incluindo operadores de busca local como 2-Opt e Or-Opt.
    -   `heuristics/greedy_routing.py`: Implementa a heurística de "Inserção Mais Barata" para construir uma rota de forma gulosa.

## 3. Explicação Detalhada do Código

### `system.py` - O Orquestrador da Simulação

A classe `System` é o ponto central.

-   **`__init__(...)`**: Inicializa o sistema com uma configuração, uma lista de veículos, a localização do depósito e configurações de buffer. Utiliza a `factory.get_strategies` para instanciar as estratégias de otimização escolhidas.
-   **`run_simulation(...)`**: O loop principal da simulação. Avança o tempo minuto a minuto, processa novos pedidos, executa a lógica de roteirização e processa eventos da fila.
-   **`process_events_due()`**: Processa todos os eventos da fila (`event_queue`) cujo timestamp é menor ou igual ao tempo atual da simulação. Cada tipo de evento (`EventType`) tem um método handler correspondente (ex: `_handle_order_ready`).
-   **`routing_decision_logic()`**: Esta é a função que decide quando e como otimizar as rotas.
    1.  Coleta os pedidos prontos (`OrderStatus.READY`) e os veículos disponíveis (`VehicleStatus.IDLE`).
    2.  Chama a estratégia de clusterização (`self.clustering_strategy.cluster(...)`) para agrupar os pedidos por veículo.
    3.  Chama a estratégia de roteirização (`self.routing_strategy.generate_routes(...)`) para encontrar a melhor sequência de visitas para cada cluster.
    4.  Aplica uma política de despacho (ASAP ou JIT) e atualiza o estado do sistema: marca veículos como `ON_ROUTE`, pedidos como `DISPATCHED` e agenda novos eventos (`VEHICLE_RETURN`, `EXPECTED_DELIVERY`).
-   **`_calculate_delayed_dispatch(...)`**: Implementa a lógica "Just-in-Time" (JIT). Calcula a folga de tempo em uma rota (diferença entre o prazo de entrega e a chegada prevista) e atrasa o início da rota para potencialmente consolidar mais pedidos futuros, sem gerar atrasos.

### `strategies.py` e `factory.py` - Padrão Strategy

-   `ClusteringStrategy` e `RoutingStrategy` são classes base abstratas que definem a interface para os algoritmos. Isso garante que o `System` possa interagir com qualquer algoritmo da mesma maneira.
-   As classes concretas (`CKMeansClustering`, `BRKGARouting`, etc.) implementam a lógica específica de cada algoritmo, atuando como adaptadores entre a entrada genérica do sistema e a chamada da função do algoritmo.
-   A função `get_strategies` em `factory.py` desacopla o `System` da criação das instâncias de estratégia, tornando o código mais limpo e fácil de estender com novos algoritmos.

### `metaheuristics/brkga.py` - Otimização Avançada

Este módulo implementa o BRKGA, uma meta-heurística poderosa para problemas de otimização combinatória.

-   **`brkga_for_routing_with_depot(...)`**: A função principal.
    1.  **Inicialização**: Converte os `datetimes` das janelas de tempo em minutos relativos a um timestamp de referência para simplificar os cálculos. Cria uma população inicial de "chaves aleatórias" (vetores de números entre 0 e 1).
    2.  **Decodificação**: A função `decode_keys_to_sequence` transforma um vetor de chaves em uma sequência de visitas, ordenando os pedidos com base nos valores das chaves.
    3.  **Avaliação (Fitness)**: Para cada sequência, a função `evaluate_sequence` (do `helpers.py`) é chamada para calcular a penalidade total e o tempo de rota.
    4.  **Evolução**: O algoritmo evolui por gerações. Em cada geração, a população é dividida em "elite" (as melhores soluções) e "não elite". Novos indivíduos são gerados pelo cruzamento (crossover) entre um pai de elite e um pai não elite, com uma probabilidade (`bias`) de herdar a chave do pai de elite. Uma porção da população é substituída por "mutantes" (soluções totalmente aleatórias) para garantir a diversidade.
    5.  **Busca Local**: Após o término das gerações, a melhor solução encontrada passa por refinamentos usando algoritmos de busca local (`two_opt`, `or_opt`, `relocate`) para tentar melhorá-la ainda mais.
    6.  **Retorno**: A função retorna a melhor sequência encontrada e um dicionário detalhado com os tempos de chegada, penalidades e horários em formato `datetime`.

### `heuristics/greedy_routing.py` - Heurística de Inserção

-   **`cheapest_insertion_heuristic(...)`**: Uma alternativa mais rápida, porém menos ótima, ao BRKGA.
    1.  **Inicialização**: Começa a rota com o ponto mais próximo do depósito.
    2.  **Iteração**: A cada passo, para todos os pedidos ainda não roteirizados, ele calcula o "custo de inserção" em todas as posições possíveis da rota atual. O custo é o aumento no tempo total da rota (`tempo(i, k) + tempo(k, j) - tempo(i, j)`).
    3.  **Seleção**: O pedido com o menor custo de inserção é adicionado à rota na sua melhor posição.
    4.  **Repetição**: O processo se repete até que todos os pedidos estejam na rota.

### `clustering/ckmeans.py` - Clusteração usando K-Means com Capacidade

Este módulo implementa uma versão do K-Means que respeita a restrição de capacidade dos clusters (veículos). É um algoritmo iterativo que alterna entre atribuição de pontos e atualização de centróides.

-   **`capacitated_kmeans(...)`**: A função principal.
    1.  **Inicialização**: Utiliza o K-Means++ padrão (`sklearn.cluster.KMeans`) para encontrar um conjunto inicial de centróides.
    2.  **Loop Iterativo**:
        -   **Etapa de Atribuição**: Esta é a parte crucial. Em vez de simplesmente atribuir cada ponto ao centróide mais próximo (como no K-Means padrão), ele resolve um Problema de Programação Inteira Mista (MIP) através da função `capacitated_assignment_mip`. O MIP garante que a atribuição minimize a distância total aos centróides, sujeito a duas restrições:
            1.  Cada ponto (entrega) deve ser atribuído a exatamente um cluster (veículo).
            2.  A soma dos "pesos" (tamanho dos pedidos) em cada cluster não pode exceder a capacidade do veículo.
        -   **Etapa de Atualização**: Após a atribuição, os centróides de cada cluster são recalculados como a média ponderada (pelo tamanho do pedido) das coordenadas dos pontos que foram atribuídos a ele.
    3.  **Convergência**: O loop continua até que a mudança na posição dos centróides entre iterações seja menor que uma tolerância (`tol`) ou o número máximo de iterações (`max_iters`) seja atingido.

### `heuristics/greedy_clustering.py` - Clusterização Gulosa Sequencial

Implementa uma heurística de clusterização simples e rápida, baseada em uma lógica gulosa.

-   **`sequential_assignment_heuristic(...)`**:
    1.  **Ordenação**: Primeiro, todas as entregas pendentes são ordenadas em ordem **decrescente** de sua distância até o depósito. A intuição é que as entregas mais distantes são mais restritivas e, portanto, devem ser alocadas primeiro para garantir que encontrem um veículo.
    2.  **Atribuição Sequencial**: O algoritmo itera sobre a lista ordenada de entregas. Para cada entrega, ele percorre a lista de veículos disponíveis.
    3.  **Primeiro Encaixe (First Fit)**: A entrega é atribuída ao **primeiro** veículo na lista que possui capacidade restante suficiente para acomodá-la.
    4.  **Finalização**: Uma vez que uma entrega é atribuída, o algoritmo passa para a próxima entrega. Se uma entrega não couber em nenhum veículo, ela é efetivamente ignorada e permanecerá pendente para a próxima rodada de roteirização.

## 4. Casos de Uso / Exemplos

O principal caso de uso é a execução de uma simulação. Isso é feito externamente ao módulo `service`, mas a interação se daria da seguinte forma:

```python
# Exemplo de como o sistema seria configurado e executado
from datetime import datetime, timedelta
import numpy as np

from service.system import System
from service.config import SimulationConfig, ClusteringAlgorithm, RoutingAlgorithm
from service.structures import Vehicle, Delivery, Point

# 1. Definir a configuração da simulação
config = SimulationConfig(
    clustering_algo=ClusteringAlgorithm.CKMEANS,
    routing_algo=RoutingAlgorithm.BRKGA
)

# 2. Criar veículos e definir o depósito
vehicles = [Vehicle(id=1, capacity=100), Vehicle(id=2, capacity=100)]
depot = np.array([-23.55, -46.63]) # Ex: São Paulo

# 3. Instanciar o sistema
system = System(config=config, vehicles=vehicles, depot_origin=depot)

# 4. Definir o cronograma de chegada de pedidos
start_time = datetime(2024, 1, 1, 8, 0)
end_time = datetime(2024, 1, 1, 18, 0)

# Pedidos que chegarão às 8:05
delivery1 = Delivery(id="d1", point=Point(lat=-23.56, lng=-46.64), size=10, preparation=5, time=30, timestamp=int(start_time.timestamp()))
delivery2 = Delivery(id="d2", point=Point(lat=-23.54, lng=-46.65), size=15, preparation=10, time=40, timestamp=int(start_time.timestamp()))

incoming_deliveries = {
    start_time + timedelta(minutes=5): [delivery1, delivery2]
}

# 5. Executar a simulação
monitor_results = system.run_simulation(
    start_time=start_time,
    end_time=end_time,
    incoming_deliveries_schedule=incoming_deliveries
)

# 6. Analisar os resultados
monitor_results.display()
```

## 5. Instruções de Instalação e Execução

### Pré-requisitos

-   Python 3.9+
-   Pip (gerenciador de pacotes)

### Instalação de Dependências

As dependências do projeto estão listadas implicitamente nos imports. Para instalar todas, execute:

```bash
pip install numpy scipy pulp scikit-learn
```

**Nota:** O `pulp` requer um solver de MIP. O `CBC` é instalado por padrão junto com ele e não requer nenhuma configuração adicional.

### Execução

O módulo `service` foi projetado para ser importado e utilizado por um script principal que orquestra a simulação. Assumindo que você tenha um arquivo `main.py` no diretório raiz do projeto (`project/`) com o código do exemplo da seção 4, você pode executá-lo da seguinte forma:

1.  Navegue até o diretório raiz do projeto no seu terminal.
2.  Execute o script principal:

```bash
python main.py
```

A saída da simulação, incluindo o log de eventos, decisões de roteamento e o painel de monitoramento, será exibida no console.
