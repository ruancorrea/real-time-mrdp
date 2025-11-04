from dataclasses import dataclass, asdict, field

# Pode ser no mesmo arquivo do System ou em um arquivo de estruturas separado
@dataclass
class Monitor:
    total_deliveries_created: int = 0
    total_deliveries_completed: int = 0
    total_deliveries_late: int = 0
    total_penalty_incurred: int = 0
    total_route_time_minutes: float = 0.0

    def get_average_penalty_per_delivery(self) -> float:
        if self.total_deliveries_completed == 0:
            return 0.0
        return self.total_penalty_incurred / self.total_deliveries_completed

    def display(self):
        """Imprime um resumo formatado do painel."""
        print("\n--- 📊 Painel de Monitoramento do Administrador ---")
        print(f"  Pedidos Criados:          {self.total_deliveries_created}")
        print(f"  Pedidos Completados:      {self.total_deliveries_completed}")
        print(f"  Pedidos Atrasados (Prazo Estourado): {self.total_deliveries_late}")
        print("-" * 45)
        print(f"  Penalidade Total Acumulada: {self.total_penalty_incurred}")
        print(f"  Penalidade Média por Entrega: {self.get_average_penalty_per_delivery():.2f}")
        print(f"  Tempo Total em Rota (min):  {self.total_route_time_minutes:.2f}")
        print("--------------------------------------------------\n")