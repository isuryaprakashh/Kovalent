const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://127.0.0.1:8000';

export async function fetchDashboardData() {
  try {
    const [podsRes, graphRes, incidentsRes] = await Promise.all([
      fetch(`${API_BASE}/api/pods`),
      fetch(`${API_BASE}/api/graph`),
      fetch(`${API_BASE}/api/orchestrator/reports`)
    ]);
    const podsData = await podsRes.json();
    const graphData = await graphRes.json();
    const incidentsData = await incidentsRes.json();
    
    return {
      pods: Array.isArray(podsData) ? podsData : [],
      graph: graphData || { nodes: [], links: [] },
      incidents: incidentsData.reports || incidentsData.incidents || []
    };
  } catch (err) {
    console.error("Failed to fetch dashboard data:", err);
    throw err;
  }
}
