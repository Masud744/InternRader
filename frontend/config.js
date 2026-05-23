const isLocal = window.location.hostname === "127.0.0.1" || window.location.hostname === "localhost";

window.INTERNRADAR_CONFIG = {
  apiBaseUrl: isLocal ? "http://127.0.0.1:8000" : "/api",
  supabaseUrl: "https://vdtvbuhhzojbqtwxhtgx.supabase.co",
  supabaseAnonKey: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZkdHZidWhoem9qYnF0d3hodGd4Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzU1ODEyNTYsImV4cCI6MjA5MTE1NzI1Nn0.nCPP70RIMvZouWIiNFoZJFjZ43q2bFlC_qlcd8FNCN0"
};
