const config = window.INTERNRADAR_CONFIG || {};
const SUPABASE_URL = config.supabaseUrl || "https://vdtvbuhhzojbqtwxhtgx.supabase.co";
const SUPABASE_ANON_KEY = config.supabaseAnonKey || "";

const isFileProtocol = window.location.protocol === "file:";
const fileProtocolMessage =
  "This page is opened via file:// which blocks network requests. Use http://127.0.0.1:5500 instead.";

console.log("Supabase.js loading...");

// Placeholder until loaded
window.auth = {
  isLoading: true,
  signUp: () => Promise.reject(new Error("Auth loading...")),
  signIn: () => Promise.reject(new Error("Auth loading...")),
  signOut: () => Promise.reject(new Error("Auth loading...")),
  resetPassword: () => Promise.reject(new Error("Auth loading...")),
  updatePassword: () => Promise.reject(new Error("Auth loading...")),
  getSession: () => Promise.resolve(null),
  getUser: () => Promise.resolve(null),
  onAuthStateChange: () => ({ data: { subscription: { unsubscribe: () => {} } } })
};

if (isFileProtocol) {
  window.auth = {
    isLoading: false,
    signUp: () => Promise.reject(new Error(fileProtocolMessage)),
    signIn: () => Promise.reject(new Error(fileProtocolMessage)),
    signOut: () => Promise.reject(new Error(fileProtocolMessage)),
    resetPassword: () => Promise.reject(new Error(fileProtocolMessage)),
    updatePassword: () => Promise.reject(new Error(fileProtocolMessage)),
    getSession: () => Promise.resolve(null),
    getUser: () => Promise.resolve(null),
    onAuthStateChange: () => ({ data: { subscription: { unsubscribe: () => {} } } })
  };
  console.warn(fileProtocolMessage);
}

function initSupabase() {
  if (typeof window.supabase === 'undefined') {
    console.log("Waiting for supabase library...");
    setTimeout(initSupabase, 200);
    return;
  }
  
  console.log("Supabase library found, initializing...");
  
  if (!SUPABASE_URL || !SUPABASE_ANON_KEY) {
    console.error("Missing Supabase URL or anon key in config.js");
    window.auth.isLoading = false;
    return;
  }

  try {
    window.supabaseClient = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
    console.log("✓ Supabase client ready");
    
    window.auth = {
      async signUp(email, password) {
        const { data, error } = await window.supabaseClient.auth.signUp({
          email,
          password,
          options: { emailRedirectTo: window.location.origin + "/index.html" }
        });
        if (error) throw new Error(error.message);
        return data;
      },

      async signIn(email, password) {
        const { data, error } = await window.supabaseClient.auth.signInWithPassword({ email, password });
        if (error) throw new Error(error.message);
        return data;
      },

      async signOut() {
        const { error } = await window.supabaseClient.auth.signOut();
        if (error) throw new Error(error.message);
      },

      async resetPassword(email) {
        const { data, error } = await window.supabaseClient.auth.resetPasswordForEmail(email, {
          redirectTo: window.location.origin + "/reset-password.html"
        });
        if (error) throw new Error(error.message);
        return data;
      },

      async updatePassword(newPassword) {
        const { data, error } = await window.supabaseClient.auth.updateUser({ password: newPassword });
        if (error) throw new Error(error.message);
        return data;
      },

      async getSession() {
        const { data: { session }, error } = await window.supabaseClient.auth.getSession();
        if (error) throw new Error(error.message);
        return session;
      },

      async getUser() {
        const { data: { user }, error } = await window.supabaseClient.auth.getUser();
        if (error) throw new Error(error.message);
        return user;
      },

      onAuthStateChange(callback) {
        return window.supabaseClient.auth.onAuthStateChange(callback);
      }
    };
    
    window.auth.isLoading = false;
    console.log("✓ Auth ready!");
  } catch (e) {
    console.error("✗ Failed:", e);
    window.auth.isLoading = false;
  }
}

if (!isFileProtocol) {
  initSupabase();
}