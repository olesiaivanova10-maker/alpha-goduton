const USE_MOCK = true; // поменять на false, когда бэкенд заработает

// согласовать с бэкендом, что будет в ответе на запрос действия, пока что просто пример
export interface ActionRequest {
  card_id: string;
  action_type: string;
}

export async function submitAction(req: ActionRequest): Promise<void> {
  if (USE_MOCK) {
    await new Promise((r) => setTimeout(r, 700));
    return;
  }
  const res = await fetch('/api/action-request', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  });
  if (!res.ok) throw new Error(`Action request failed: ${res.status}`);
}