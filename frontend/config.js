const isLocal = window.location.hostname === "127.0.0.1" || window.location.hostname === "localhost";

window.INTERNRADAR_CONFIG = {
  apiBaseUrl: isLocal ? "http://127.0.0.1:8000" : "/api",
  supabaseUrl: "https://uwjinixfmfvxafjikzrd.supabase.co",
  supabaseAnonKey: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InV3amluaXhmbWZ2eGFmamlrenJkIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODAzMjMzNjgsImV4cCI6MjA5NTg5OTM2OH0.3fzL4beQhoDZOjKF1VxWoVc3-LuCYDCESwTJqnujzcQ"
};
