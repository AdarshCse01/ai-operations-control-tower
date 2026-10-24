import { useEffect, useState } from "react";
import {
  Activity,
  AlertTriangle,
  ArrowUpRight,
  BarChart3,
  Boxes,
  BrainCircuit,
  Calendar,
  Check,
  CheckCircle2,
  CircleHelp,
  Database,
  Factory,
  FileText,
  Info,
  Lock,
  LogOut,
  Package,
  Plus,
  RefreshCw,
  Search,
  ShieldAlert,
  TrendingUp,
  Truck,
  UserCheck,
  Warehouse as WarehouseIcon,
  X,
} from "lucide-react";

const getApiBaseUrl = (): string => {
  const envUrl = (import.meta as any).env?.VITE_API_URL;
  if (envUrl && typeof envUrl === "string" && envUrl.trim() !== "") {
    return envUrl.trim().replace(/\/+$/, "");
  }
  if (typeof window !== "undefined" && window.location) {
    const { protocol, hostname } = window.location;
    if (hostname && hostname !== "localhost" && hostname !== "127.0.0.1") {
      return `${protocol}//${hostname}:8000/api/v1`;
    }
  }
  return "http://localhost:8000/api/v1";
};

const API = getApiBaseUrl();
const isDemoLoginsEnabled: boolean =
  (import.meta as any).env?.VITE_ENABLE_DEMO_LOGINS === "true" ||
  ((import.meta as any).env?.DEV && (import.meta as any).env?.VITE_ENABLE_DEMO_LOGINS !== "false");

// Types
type Trend = { day: string; orders: number; late: number };
type Snapshot = { kpis: Record<string, number>; trend: Trend[]; data_mode?: string };

type DateRangeInfo = {
  label: string;
  start_date: string | null;
  end_date: string | null;
  preset: string | null;
};

type OrderTrendPoint = {
  date: string;
  orders_count: number;
  delivered_count: number;
  delayed_count: number;
  total_revenue: string;
};

type OrderStatusItem = {
  status: string;
  count: number;
  percentage: number;
  total_amount: string;
};

type WarehouseStockItem = {
  warehouse_id: string;
  warehouse_code: string;
  warehouse_name: string;
  total_units: number;
  available_units: number;
  reserved_units: number;
  valuation: string;
  sku_count: number;
};

type CategoryStockItem = {
  category: string;
  total_units: number;
  valuation: string;
  sku_count: number;
};

type LowStockAlertItem = {
  inventory_id: string;
  product_id: string;
  product_sku: string;
  product_name: string;
  product_category: string;
  warehouse_code: string;
  warehouse_name: string;
  quantity_on_hand: number;
  quantity_reserved: number;
  available_quantity: number;
  reorder_quantity: number;
  safety_stock: number;
  unit_cost: string;
  status: "STOCKOUT" | "LOW_STOCK";
};

type FulfillmentMetrics = {
  data_mode: string;
  has_sufficient_data: boolean;
  total_delivered_orders: number;
  delivered_with_targets: number;
  on_time_count: number;
  delayed_count: number;
  on_time_rate: number | null;
  average_fulfillment_days: number | null;
  status_message: string;
};

type SupplierPerformanceItem = {
  supplier_id: string;
  code: string;
  name: string;
  lead_time_days: number;
  reliability_score: number;
  active_products_count: number;
  is_active: boolean;
};

type SupplierPerformance = {
  data_mode: string;
  has_sufficient_data: boolean;
  total_suppliers: number;
  average_reliability_score: number | null;
  average_lead_time_days: number | null;
  suppliers: SupplierPerformanceItem[];
  transparency_note: string;
};

type ExecutiveDashboardKPIs = {
  total_orders: number;
  active_orders: number;
  delivered_orders: number;
  cancelled_orders: number;
  total_order_valuation: string;
  total_inventory_units: number;
  available_inventory_units: number;
  reserved_inventory_units: number;
  total_inventory_valuation: string;
  low_stock_items_count: number;
  stockout_items_count: number;
  pending_recommendations_count: number;
  critical_risks_count: number;
  on_time_fulfillment_rate: number | null;
  average_supplier_reliability: number | null;
};

type ExecutiveDashboardData = {
  generated_at: string;
  data_mode: string;
  date_range: DateRangeInfo;
  kpis: ExecutiveDashboardKPIs;
  order_status_distribution: OrderStatusItem[];
  order_volume_trend: OrderTrendPoint[];
  warehouse_stock: WarehouseStockItem[];
  category_stock: CategoryStockItem[];
  low_stock_alerts: LowStockAlertItem[];
  fulfillment_summary: FulfillmentMetrics;
  supplier_summary: SupplierPerformance;
  critical_risks_preview: any[];
  pending_recommendations_preview: any[];
};

type Risk = {
  id: string;
  category: string;
  severity: string;
  score: number;
  entity_type: string;
  entity_id: string;
  entity_name: string;
  rules_triggered?: string[];
  metrics?: Record<string, any>;
  explanation: string;
  suggested_action?: string;
  calculated_at?: string;
  source?: string;
  supplier?: string;
  message?: string;
};

type Recommendation = {
  id: string;
  recommendation_type?: string;
  priority?: string;
  title: string;
  entity_type?: string;
  entity_id?: string;
  entity_name?: string;
  evidence?: Record<string, any> | null;
  explanation?: string;
  proposed_action?: string;
  parameters?: Record<string, any> | null;
  status?: "PENDING" | "APPROVED" | "REJECTED" | "EXECUTED" | string;
  decided_at?: string | null;
  decided_by_name?: string | null;
  decision_comment?: string | null;
  executed_at?: string | null;
  execution_result?: Record<string, any> | null;
  created_at?: string;
  action?: string;
  reason?: string;
  risk_score?: number;
};

type OperationalSummary = {
  total_products: number;
  active_products: number;
  total_inventory_units: number;
  reserved_inventory_units: number;
  available_inventory_units: number;
  low_stock_items_count: number;
  stockout_items_count: number;
  total_inventory_valuation: string;
  total_orders: number;
  pending_orders: number;
  processing_orders: number;
  shipped_orders: number;
  delivered_orders: number;
  cancelled_orders: number;
  on_time_fulfillment_rate: number | null;
  total_movement_volume: number;
};

type MLEvaluationMetrics = {
  model_name: string;
  task_type: string;
  status: "evaluated" | "insufficient_data";
  samples_count: number;
  accuracy: number | null;
  precision: number | null;
  recall: number | null;
  f1_score: number | null;
  mae: number | null;
  baseline_comparison: Record<string, any> | null;
  data_requirements: string[] | null;
  evaluation_notes: string;
};

type UserProfile = {
  id: string;
  email: string;
  full_name: string;
  role: "ADMIN" | "OPERATIONS_MANAGER" | "ANALYST" | "VIEWER";
  is_active: boolean;
  permissions: string[];
};


type Supplier = {
  id: string;
  code: string;
  name: string;
  contact_email: string | null;
  contact_phone: string | null;
  lead_time_days: number;
  reliability_score: string;
  is_active: boolean;
};

type Product = {
  id: string;
  sku: string;
  name: string;
  description: string | null;
  category: string;
  unit_price: string;
  unit_cost: string;
  reorder_point: number;
  safety_stock: number;
  supplier_id: string | null;
  supplier_name?: string | null;
  is_active: boolean;
};

type Warehouse = {
  id: string;
  code: string;
  name: string;
  location: string;
  capacity: number;
  is_active: boolean;
};

type InventoryItem = {
  id: string;
  product_id: string;
  warehouse_id: string;
  product_sku?: string | null;
  product_name?: string | null;
  product_category?: string | null;
  warehouse_code?: string | null;
  warehouse_name?: string | null;
  quantity_on_hand: number;
  quantity_reserved: number;
  available_quantity: number;
  reorder_quantity: number;
};

type StockMovement = {
  id: string;
  product_sku?: string | null;
  warehouse_code?: string | null;
  movement_type: string;
  quantity: number;
  reference: string;
  actor_name: string;
  created_at: string;
};

type OrderItem = {
  id: string;
  product_id: string;
  product_sku?: string | null;
  product_name?: string | null;
  quantity: number;
  unit_price: string;
  subtotal: string;
};

type Order = {
  id: string;
  order_number: string;
  customer_name: string;
  status: "PENDING" | "PROCESSING" | "SHIPPED" | "DELIVERED" | "CANCELLED";
  priority: "LOW" | "NORMAL" | "HIGH" | "CRITICAL";
  total_amount: string;
  warehouse_id: string | null;
  warehouse_code?: string | null;
  created_by_name?: string | null;
  created_at: string;
  items: OrderItem[];
};

type PaginatedResult<T> = {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
};

export function App() {
  const [currentUser, setCurrentUser] = useState<UserProfile | null>(null);
  const [token, setToken] = useState<string>("");
  const [authChecking, setAuthChecking] = useState<boolean>(true);

  // Auth Form State
  const [authMode, setAuthMode] = useState<"login" | "register">("login");
  const [authEmail, setAuthEmail] = useState("");
  const [authPassword, setAuthPassword] = useState("");
  const [authFullName, setAuthFullName] = useState("");
  const [authRole, setAuthRole] = useState<string>("OPERATIONS_MANAGER");
  const [authError, setAuthError] = useState("");
  const [authBusy, setAuthBusy] = useState(false);

  // Active Navigation Tab
  const [activeTab, setActiveTab] = useState<
    "command-center" | "orders" | "inventory" | "products" | "suppliers" | "warehouses" | "risks" | "approvals" | "analytics"
  >("command-center");

  // Dashboard Data State
  const [data, setData] = useState<Snapshot | null>(null);
  const [risks, setRisks] = useState<Risk[]>([]);
  const [recs, setRecs] = useState<Recommendation[]>([]);
  const [recStatusFilter, setRecStatusFilter] = useState<string>("ALL");
  const [analyticsSummary, setAnalyticsSummary] = useState<OperationalSummary | null>(null);
  const [mlEvaluation, setMlEvaluation] = useState<MLEvaluationMetrics | null>(null);
  const [dashboardBusy, setDashboardBusy] = useState(false);

  // Phase 6 Executive Analytics State
  const [dashboardRange, setDashboardRange] = useState<string>("30d");
  const [customStartDate, setCustomStartDate] = useState<string>("");
  const [customEndDate, setCustomEndDate] = useState<string>("");
  const [dataSourceMode, setDataSourceMode] = useState<"live" | "demo">("live");
  const [executiveData, setExecutiveData] = useState<ExecutiveDashboardData | null>(null);
  const [executiveError, setExecutiveError] = useState<string>("");


  // Operational State: Suppliers
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [supplierTotal, setSupplierTotal] = useState(0);
  const [supplierPage, setSupplierPage] = useState(1);
  const [supplierSearch, setSupplierSearch] = useState("");
  const [supplierModal, setSupplierModal] = useState(false);

  // Operational State: Products
  const [products, setProducts] = useState<Product[]>([]);
  const [productTotal, setProductTotal] = useState(0);
  const [productPage, setProductPage] = useState(1);
  const [productSearch, setProductSearch] = useState("");
  const [productCategory, setProductCategory] = useState("");
  const [productModal, setProductModal] = useState(false);

  // Operational State: Warehouses
  const [warehouses, setWarehouses] = useState<Warehouse[]>([]);
  const [warehouseTotal, setWarehouseTotal] = useState(0);
  const [warehousePage, setWarehousePage] = useState(1);
  const [warehouseSearch, setWarehouseSearch] = useState("");
  const [warehouseModal, setWarehouseModal] = useState(false);

  // Operational State: Inventory
  const [inventoryItems, setInventoryItems] = useState<InventoryItem[]>([]);
  const [inventoryTotal, setInventoryTotal] = useState(0);
  const [inventoryPage, setInventoryPage] = useState(1);
  const [inventorySearch, setInventorySearch] = useState("");
  const [lowStockFilter, setLowStockFilter] = useState(false);
  const [inventorySubTab, setInventorySubTab] = useState<"balances" | "movements">("balances");
  const [movements, setMovements] = useState<StockMovement[]>([]);
  const [movementTotal, setMovementTotal] = useState(0);
  const [receiptModal, setReceiptModal] = useState(false);
  const [issueModal, setIssueModal] = useState(false);

  // Operational State: Orders
  const [ordersList, setOrdersList] = useState<Order[]>([]);
  const [orderTotal, setOrderTotal] = useState(0);
  const [orderPage, setOrderPage] = useState(1);
  const [orderSearch, setOrderSearch] = useState("");
  const [orderStatusFilter, setOrderStatusFilter] = useState("");
  const [orderModal, setOrderModal] = useState(false);
  const [selectedOrder, setSelectedOrder] = useState<Order | null>(null);

  // Shared State
  const [globalError, setGlobalError] = useState("");
  const [globalSuccess, setGlobalSuccess] = useState("");
  const [loading, setLoading] = useState(false);

  // Form states
  const [supplierForm, setSupplierForm] = useState({
    code: "",
    name: "",
    contact_email: "",
    contact_phone: "",
    lead_time_days: 7,
    reliability_score: "0.95",
  });

  const [productForm, setProductForm] = useState({
    sku: "",
    name: "",
    description: "",
    category: "Hardware",
    unit_price: "10.00",
    unit_cost: "5.00",
    reorder_point: 10,
    safety_stock: 5,
    supplier_id: "",
  });

  const [warehouseForm, setWarehouseForm] = useState({
    code: "",
    name: "",
    location: "",
    capacity: 10000,
  });

  const [receiptForm, setReceiptForm] = useState({
    product_id: "",
    warehouse_id: "",
    quantity: 10,
    reference: "",
  });

  const [issueForm, setIssueForm] = useState({
    product_id: "",
    warehouse_id: "",
    quantity: 5,
    reference: "",
  });

  const [orderForm, setOrderForm] = useState({
    customer_name: "",
    priority: "NORMAL",
    warehouse_id: "",
    items: [{ product_id: "", quantity: 1 }],
  });

  // Check session on load
  useEffect(() => {
    async function checkSession() {
      try {
        const res = await fetch(`${API}/auth/me`, {
          credentials: "include",
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        });
        if (res.ok) {
          const profile: UserProfile = await res.json();
          setCurrentUser(profile);
        }
      } catch {
        // Not authenticated
      } finally {
        setAuthChecking(false);
      }
    }
    void checkSession();
  }, [token]);

  // Auth fetch helper
  async function fetchWithAuth(url: string, options: RequestInit = {}) {
    const headers: Record<string, string> = {
      "X-Requested-With": "XMLHttpRequest",
      ...(options.headers as Record<string, string>),
    };
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }
    const res = await fetch(url, {
      ...options,
      credentials: "include",
      headers,
    });
    if (res.status === 401) {
      setCurrentUser(null);
      setToken("");
      throw new Error("Session expired. Please sign in again.");
    }
    return res;
  }

  // Load dashboard and executive analytics
  async function loadDashboard(rangeOverride?: string, startOverride?: string, endOverride?: string) {
    if (!currentUser) return;
    setDashboardBusy(true);
    setGlobalError("");
    setExecutiveError("");
    try {
      const activeRange = rangeOverride !== undefined ? rangeOverride : dashboardRange;
      const activeStart = startOverride !== undefined ? startOverride : customStartDate;
      const activeEnd = endOverride !== undefined ? endOverride : customEndDate;

      const execParams = new URLSearchParams();
      if (activeRange) execParams.append("range", activeRange);
      if (activeRange === "custom") {
        if (activeStart) execParams.append("start_date", activeStart);
        if (activeEnd) execParams.append("end_date", activeEnd);
      }

      const calls: Promise<Response>[] = [
        fetchWithAuth(`${API}/dashboard/summary?source=demo`),
        fetchWithAuth(`${API}/recommendations`),
        fetchWithAuth(`${API}/analytics/summary`),
        fetchWithAuth(`${API}/analytics/executive?${execParams.toString()}`),
      ];
      const hasAnalytics = currentUser.permissions.includes("analytics:read");
      if (hasAnalytics) {
        calls.push(fetchWithAuth(`${API}/risks`));
        calls.push(fetchWithAuth(`${API}/analytics/ml-evaluation`));
      }
      const results = await Promise.all(calls);
      const d = await results[0].json();
      const c = await results[1].json();
      const a = await results[2].json();
      setData(d);
      setRecs(c.items || []);
      setAnalyticsSummary(a);

      if (results[3].ok) {
        const exec = await results[3].json();
        setExecutiveData(exec);
      } else {
        const errJson = await results[3].json().catch(() => ({}));
        setExecutiveError(errJson.detail || "Failed to load executive intelligence.");
      }

      if (hasAnalytics && results[4]) {
        const r = await results[4].json();
        setRisks(r.items || []);
      }
      if (hasAnalytics && results[5]) {
        const ml = await results[5].json();
        setMlEvaluation(ml);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load dashboard intelligence";
      setGlobalError(msg);
      setExecutiveError(msg);
    } finally {
      setDashboardBusy(false);
    }
  }


  // Load Suppliers
  async function loadSuppliers() {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        page: supplierPage.toString(),
        page_size: "15",
      });
      if (supplierSearch.trim()) params.append("search", supplierSearch.trim());
      const res = await fetchWithAuth(`${API}/suppliers?${params.toString()}`);
      if (res.ok) {
        const body: PaginatedResult<Supplier> = await res.json();
        setSuppliers(body.items);
        setSupplierTotal(body.total);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load suppliers";
      setGlobalError(msg);
    } finally {
      setLoading(false);
    }
  }

  // Load Products
  async function loadProducts() {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        page: productPage.toString(),
        page_size: "15",
      });
      if (productSearch.trim()) params.append("search", productSearch.trim());
      if (productCategory.trim()) params.append("category", productCategory.trim());
      const res = await fetchWithAuth(`${API}/products?${params.toString()}`);
      if (res.ok) {
        const body: PaginatedResult<Product> = await res.json();
        setProducts(body.items);
        setProductTotal(body.total);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load products";
      setGlobalError(msg);
    } finally {
      setLoading(false);
    }
  }

  // Load Warehouses
  async function loadWarehouses() {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        page: warehousePage.toString(),
        page_size: "15",
      });
      if (warehouseSearch.trim()) params.append("search", warehouseSearch.trim());
      const res = await fetchWithAuth(`${API}/warehouses?${params.toString()}`);
      if (res.ok) {
        const body: PaginatedResult<Warehouse> = await res.json();
        setWarehouses(body.items);
        setWarehouseTotal(body.total);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load warehouses";
      setGlobalError(msg);
    } finally {
      setLoading(false);
    }
  }

  // Load Inventory & Movements
  async function loadInventory() {
    setLoading(true);
    try {
      if (inventorySubTab === "balances") {
        const params = new URLSearchParams({
          page: inventoryPage.toString(),
          page_size: "15",
        });
        if (inventorySearch.trim()) params.append("search", inventorySearch.trim());
        if (lowStockFilter) params.append("low_stock_only", "true");
        const res = await fetchWithAuth(`${API}/inventory?${params.toString()}`);
        if (res.ok) {
          const body: PaginatedResult<InventoryItem> = await res.json();
          setInventoryItems(body.items);
          setInventoryTotal(body.total);
        }
      } else {
        const params = new URLSearchParams({
          page: inventoryPage.toString(),
          page_size: "15",
        });
        const res = await fetchWithAuth(`${API}/inventory/movements?${params.toString()}`);
        if (res.ok) {
          const body: PaginatedResult<StockMovement> = await res.json();
          setMovements(body.items);
          setMovementTotal(body.total);
        }
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load inventory";
      setGlobalError(msg);
    } finally {
      setLoading(false);
    }
  }

  // Load Orders
  async function loadOrders() {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        page: orderPage.toString(),
        page_size: "15",
      });
      if (orderSearch.trim()) params.append("search", orderSearch.trim());
      if (orderStatusFilter.trim()) params.append("status", orderStatusFilter.trim());
      const res = await fetchWithAuth(`${API}/orders?${params.toString()}`);
      if (res.ok) {
        const body: PaginatedResult<Order> = await res.json();
        setOrdersList(body.items);
        setOrderTotal(body.total);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load orders";
      setGlobalError(msg);
    } finally {
      setLoading(false);
    }
  }

  // Trigger loads based on activeTab
  useEffect(() => {
    if (!currentUser) return;
    if (activeTab === "command-center") void loadDashboard();
    else if (activeTab === "suppliers") void loadSuppliers();
    else if (activeTab === "products") {
      void loadProducts();
      void loadSuppliers();
    } else if (activeTab === "warehouses") void loadWarehouses();
    else if (activeTab === "inventory") {
      void loadInventory();
      void loadProducts();
      void loadWarehouses();
    } else if (activeTab === "orders") {
      void loadOrders();
      void loadProducts();
      void loadWarehouses();
    }
  }, [
    currentUser,
    activeTab,
    supplierPage,
    productPage,
    warehousePage,
    inventoryPage,
    inventorySubTab,
    lowStockFilter,
    orderPage,
    orderStatusFilter,
  ]);

  // Auth Handlers
  async function handleLogin(e?: React.FormEvent) {
    if (e) e.preventDefault();
    setAuthBusy(true);
    setAuthError("");
    try {
      const res = await fetch(`${API}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ email: authEmail, password: authPassword }),
      });
      if (!res.ok) {
        const body = await res.json();
        throw new Error(body.detail || "Authentication failed");
      }
      const data = await res.json();
      setToken(data.access_token);
      const meRes = await fetch(`${API}/auth/me`, {
        headers: { Authorization: `Bearer ${data.access_token}` },
        credentials: "include",
      });
      const profile = await meRes.json();
      setCurrentUser(profile);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Invalid credentials";
      setAuthError(msg);
    } finally {
      setAuthBusy(false);
    }
  }

  async function handleRegister(e: React.FormEvent) {
    e.preventDefault();
    setAuthBusy(true);
    setAuthError("");
    try {
      const res = await fetch(`${API}/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          email: authEmail,
          password: authPassword,
          full_name: authFullName,
          role: authRole,
        }),
      });
      if (!res.ok) {
        const body = await res.json();
        const detailMsg = Array.isArray(body.detail) ? body.detail[0]?.msg : body.detail;
        throw new Error(detailMsg || "Registration failed");
      }
      await handleLogin();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Could not create account";
      setAuthError(msg);
    } finally {
      setAuthBusy(false);
    }
  }

  async function handleQuickDemoLogin(demoEmail: string, demoRole: string, demoName: string) {
    setAuthEmail(demoEmail);
    setAuthPassword("DemoPass123");
    setAuthBusy(true);
    setAuthError("");
    try {
      const loginRes = await fetch(`${API}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ email: demoEmail, password: "DemoPass123" }),
      });
      if (loginRes.ok) {
        const body = await loginRes.json();
        setToken(body.access_token);
        const meRes = await fetch(`${API}/auth/me`, {
          headers: { Authorization: `Bearer ${body.access_token}` },
          credentials: "include",
        });
        setCurrentUser(await meRes.json());
        return;
      }
      const regRes = await fetch(`${API}/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          email: demoEmail,
          password: "DemoPass123",
          full_name: demoName,
          role: demoRole,
        }),
      });
      if (regRes.ok) {
        const logRes2 = await fetch(`${API}/auth/login`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({ email: demoEmail, password: "DemoPass123" }),
        });
        const body2 = await logRes2.json();
        setToken(body2.access_token);
        const meRes = await fetch(`${API}/auth/me`, {
          headers: { Authorization: `Bearer ${body2.access_token}` },
          credentials: "include",
        });
        setCurrentUser(await meRes.json());
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Quick login failed";
      setAuthError(msg);
    } finally {
      setAuthBusy(false);
    }
  }

  async function handleLogout() {
    try {
      await fetch(`${API}/auth/logout`, { method: "POST", credentials: "include" });
    } catch {
      // Offline logout
    }
    setCurrentUser(null);
    setToken("");
    setData(null);
    setRisks([]);
    setRecs([]);
  }

  // Mutation Handlers
  const canManageData = currentUser?.permissions.includes("data:manage") ?? false;
  const canDecide = currentUser?.permissions.includes("recommendations:decide") ?? false;
  const canViewAnalytics = currentUser?.permissions.includes("analytics:read") ?? false;

  async function handleCreateSupplier(e: React.FormEvent) {
    e.preventDefault();
    setGlobalError("");
    try {
      const res = await fetchWithAuth(`${API}/suppliers`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...supplierForm,
          contact_email: supplierForm.contact_email || null,
          contact_phone: supplierForm.contact_phone || null,
        }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to create supplier");
      }
      setGlobalSuccess(`Supplier '${supplierForm.name}' created successfully.`);
      setSupplierModal(false);
      setSupplierForm({
        code: "",
        name: "",
        contact_email: "",
        contact_phone: "",
        lead_time_days: 7,
        reliability_score: "0.95",
      });
      void loadSuppliers();
    } catch (err: unknown) {
      setGlobalError(err instanceof Error ? err.message : "Operation failed");
    }
  }

  async function handleDeactivateSupplier(id: string) {
    if (!confirm("Are you sure you want to deactivate this supplier?")) return;
    try {
      const res = await fetchWithAuth(`${API}/suppliers/${id}/deactivate`, { method: "POST" });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to deactivate");
      }
      setGlobalSuccess("Supplier deactivated successfully.");
      void loadSuppliers();
    } catch (err: unknown) {
      setGlobalError(err instanceof Error ? err.message : "Operation failed");
    }
  }

  async function handleCreateProduct(e: React.FormEvent) {
    e.preventDefault();
    setGlobalError("");
    try {
      const res = await fetchWithAuth(`${API}/products`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...productForm,
          supplier_id: productForm.supplier_id || null,
        }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to create product");
      }
      setGlobalSuccess(`Product '${productForm.sku}' created successfully.`);
      setProductModal(false);
      setProductForm({
        sku: "",
        name: "",
        description: "",
        category: "Hardware",
        unit_price: "10.00",
        unit_cost: "5.00",
        reorder_point: 10,
        safety_stock: 5,
        supplier_id: "",
      });
      void loadProducts();
    } catch (err: unknown) {
      setGlobalError(err instanceof Error ? err.message : "Operation failed");
    }
  }

  async function handleDeactivateProduct(id: string) {
    if (!confirm("Are you sure you want to deactivate this product?")) return;
    try {
      const res = await fetchWithAuth(`${API}/products/${id}/deactivate`, { method: "POST" });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to deactivate");
      }
      setGlobalSuccess("Product deactivated successfully.");
      void loadProducts();
    } catch (err: unknown) {
      setGlobalError(err instanceof Error ? err.message : "Operation failed");
    }
  }

  async function handleCreateWarehouse(e: React.FormEvent) {
    e.preventDefault();
    setGlobalError("");
    try {
      const res = await fetchWithAuth(`${API}/warehouses`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(warehouseForm),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to create warehouse");
      }
      setGlobalSuccess(`Warehouse '${warehouseForm.code}' created successfully.`);
      setWarehouseModal(false);
      setWarehouseForm({ code: "", name: "", location: "", capacity: 10000 });
      void loadWarehouses();
    } catch (err: unknown) {
      setGlobalError(err instanceof Error ? err.message : "Operation failed");
    }
  }

  async function handleReceiveStock(e: React.FormEvent) {
    e.preventDefault();
    setGlobalError("");
    try {
      const idemp = `rec-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
      const res = await fetchWithAuth(`${API}/inventory/receipt`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...receiptForm,
          idempotency_key: idemp,
        }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Receipt operation failed");
      }
      setGlobalSuccess("Inbound stock received and movement recorded.");
      setReceiptModal(false);
      void loadInventory();
    } catch (err: unknown) {
      setGlobalError(err instanceof Error ? err.message : "Operation failed");
    }
  }

  async function handleIssueStock(e: React.FormEvent) {
    e.preventDefault();
    setGlobalError("");
    try {
      const idemp = `iss-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
      const res = await fetchWithAuth(`${API}/inventory/issue`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...issueForm,
          idempotency_key: idemp,
        }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Issue operation failed");
      }
      setGlobalSuccess("Outbound stock issued and movement recorded.");
      setIssueModal(false);
      void loadInventory();
    } catch (err: unknown) {
      setGlobalError(err instanceof Error ? err.message : "Operation failed");
    }
  }

  async function handleCreateOrder(e: React.FormEvent) {
    e.preventDefault();
    setGlobalError("");
    try {
      const validItems = orderForm.items.filter((it) => it.product_id && it.quantity > 0);
      if (validItems.length === 0) {
        throw new Error("Order must contain at least one valid line item");
      }
      const res = await fetchWithAuth(`${API}/orders`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          customer_name: orderForm.customer_name,
          priority: orderForm.priority,
          warehouse_id: orderForm.warehouse_id || null,
          items: validItems,
        }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to create order");
      }
      const created: Order = await res.json();
      setGlobalSuccess(`Order ${created.order_number} created with total $${created.total_amount}.`);
      setOrderModal(false);
      setOrderForm({
        customer_name: "",
        priority: "NORMAL",
        warehouse_id: "",
        items: [{ product_id: "", quantity: 1 }],
      });
      void loadOrders();
    } catch (err: unknown) {
      setGlobalError(err instanceof Error ? err.message : "Operation failed");
    }
  }

  async function handleUpdateOrderStatus(orderId: string, nextStatus: string) {
    setGlobalError("");
    try {
      const res = await fetchWithAuth(`${API}/orders/${orderId}/status`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          status: nextStatus,
          comment: `Status transitioned to ${nextStatus} via Control Tower UI`,
        }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Status transition rejected");
      }
      const updated: Order = await res.json();
      setSelectedOrder(updated);
      setGlobalSuccess(`Order status transitioned to ${nextStatus}.`);
      void loadOrders();
    } catch (err: unknown) {
      setGlobalError(err instanceof Error ? err.message : "Status transition failed");
    }
  }

  async function handleApproval(id: string, approved: boolean) {
    setGlobalError("");
    try {
      const res = await fetchWithAuth(`${API}/recommendations/${id}/approval`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          approved,
          comment: approved ? "Approved via Control Tower interface" : "Rejected by operator",
        }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Approval decision recording failed");
      }
      setGlobalSuccess(`Recommendation ${approved ? "approved" : "rejected"}. Audit trail entry generated.`);
      void loadDashboard();
    } catch (err: unknown) {
      setGlobalError(err instanceof Error ? err.message : "Operation failed");
    }
  }

  async function handleExecute(id: string) {
    setGlobalError("");
    try {
      const res = await fetchWithAuth(`${API}/recommendations/${id}/execute`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ comment: "Safe idempotent execution from Control Tower UI" }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Execution failed");
      }
      const data = await res.json();
      const actionName = data.execution_result?.action || "action";
      setGlobalSuccess(`Proposal executed safely (${actionName}). Operational state updated and audit log recorded.`);
      void loadDashboard();
    } catch (err: unknown) {
      setGlobalError(err instanceof Error ? err.message : "Execution failed");
    }
  }


  if (authChecking) {
    return (
      <div className="auth-screen">
        <div style={{ color: "#fff", display: "flex", alignItems: "center", gap: 10 }}>
          <RefreshCw size={18} className="spin" /> Verifying secure credentials…
        </div>
      </div>
    );
  }

  // Auth Screen
  if (!currentUser) {
    return (
      <div className="auth-screen">
        <div className="auth-box">
          <div className="auth-brand">
            <span className="brand-mark">
              <BrainCircuit size={22} />
            </span>
            <div>
              <span className="title">
                Ops<span style={{ color: "#818cf8" }}>Control</span> Tower
              </span>
              <small>PHASE 4 · REAL BUSINESS OPERATIONS</small>
            </div>
          </div>

          <div className="auth-tabs">
            <button
              type="button"
              className={`auth-tab ${authMode === "login" ? "active" : ""}`}
              onClick={() => setAuthMode("login")}
            >
              Sign In
            </button>
            <button
              type="button"
              className={`auth-tab ${authMode === "register" ? "active" : ""}`}
              onClick={() => setAuthMode("register")}
            >
              Create Account
            </button>
          </div>

          {authError && (
            <div className="error-banner">
              <AlertTriangle size={15} /> <span>{authError}</span>
            </div>
          )}

          <form onSubmit={authMode === "login" ? handleLogin : handleRegister} className="auth-form">
            {authMode === "register" && (
              <div className="form-field">
                <label>Full Name</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Adarsh Singh"
                  value={authFullName}
                  onChange={(e) => setAuthFullName(e.target.value)}
                />
              </div>
            )}

            <div className="form-field">
              <label>Work Email</label>
              <input
                type="email"
                required
                placeholder="operator@opscontrol.internal"
                value={authEmail}
                onChange={(e) => setAuthEmail(e.target.value)}
              />
            </div>

            <div className="form-field">
              <label>Password (min. 8 characters with letter & number)</label>
              <input
                type="password"
                required
                placeholder="••••••••••••"
                value={authPassword}
                onChange={(e) => setAuthPassword(e.target.value)}
              />
            </div>

            {authMode === "register" && (
              <div className="form-field">
                <label>Assigned Role (RBAC)</label>
                <select value={authRole} onChange={(e) => setAuthRole(e.target.value)}>
                  <option value="VIEWER">VIEWER (Read-only dashboard)</option>
                  <option value="ANALYST">ANALYST (Operational analytics & risks)</option>
                  <option value="OPERATIONS_MANAGER">OPERATIONS_MANAGER (Business Operations & Data)</option>
                  <option value="ADMIN">ADMIN (Full administrative privileges)</option>
                </select>
              </div>
            )}

            <button type="submit" className="auth-submit" disabled={authBusy}>
              {authBusy ? (
                <>
                  <RefreshCw size={14} className="spin" style={{ display: "inline", marginRight: 6 }} />
                  Processing…
                </>
              ) : authMode === "login" ? (
                "Authenticate & Open Tower →"
              ) : (
                "Create Account & Sign In →"
              )}
            </button>
          </form>

          {isDemoLoginsEnabled && (
            <div className="demo-pills-box">
              <div className="demo-pills-title">QUICK EVALUATOR DEMO LOGINS (ONE-CLICK)</div>
              <div className="demo-pills-grid">
                <button
                  type="button"
                  className="demo-pill-btn"
                  onClick={() =>
                    void handleQuickDemoLogin(
                      "manager@opscontrol.internal",
                      "OPERATIONS_MANAGER",
                      "Marcus Vance"
                    )
                  }
                >
                  <b>
                    <UserCheck size={13} style={{ color: "#60a5fa" }} /> Operations Mgr
                  </b>
                  <small>Business Writes & Data</small>
                </button>
                <button
                  type="button"
                  className="demo-pill-btn"
                  onClick={() =>
                    void handleQuickDemoLogin("admin@opscontrol.internal", "ADMIN", "Adarsh Singh (Admin)")
                  }
                >
                  <b>
                    <ShieldAlert size={13} style={{ color: "#c084fc" }} /> Admin
                  </b>
                  <small>Full Access</small>
                </button>
                <button
                  type="button"
                  className="demo-pill-btn"
                  onClick={() =>
                    void handleQuickDemoLogin("analyst@opscontrol.internal", "ANALYST", "Elena Rostova")
                  }
                >
                  <b>
                    <TrendingUp size={13} style={{ color: "#fb923c" }} /> Analyst
                  </b>
                  <small>Read + Risk Analytics</small>
                </button>
                <button
                  type="button"
                  className="demo-pill-btn"
                  onClick={() =>
                    void handleQuickDemoLogin("viewer@opscontrol.internal", "VIEWER", "Guest Auditor")
                  }
                >
                  <b>
                    <Lock size={13} style={{ color: "#4ade80" }} /> Viewer
                  </b>
                  <small>Read-only Observer</small>
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    );
  }

  // Authenticated Workspace
  const userInitials =
    currentUser.full_name
      .split(" ")
      .map((n) => n[0])
      .slice(0, 2)
      .join("")
      .toUpperCase() || "OP";

  return (
    <div className="app-shell">
      {/* Sidebar Navigation */}
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">
            <BrainCircuit size={21} />
          </span>
          <span>
            Ops<span className="brand-light">Control</span>
            <small>REAL BUSINESS OPERATIONS</small>
          </span>
        </div>

        <div className="workspace">
          <span className="workspace-dot" /> Acme Global Operations <span className="chevron">⌄</span>
        </div>

        <p className="nav-label">OPERATIONS DOMAIN</p>
        <div
          className={`nav ${activeTab === "command-center" ? "active" : ""}`}
          onClick={() => setActiveTab("command-center")}
          style={{ cursor: "pointer" }}
        >
          <Activity /> <span>Executive Dashboard</span>
        </div>
        <div
          className={`nav ${activeTab === "orders" ? "active" : ""}`}
          onClick={() => setActiveTab("orders")}
          style={{ cursor: "pointer" }}
        >
          <Package /> <span>Orders</span>
          <em>{orderTotal > 0 ? orderTotal : "Live"}</em>
        </div>
        <div
          className={`nav ${activeTab === "inventory" ? "active" : ""}`}
          onClick={() => setActiveTab("inventory")}
          style={{ cursor: "pointer" }}
        >
          <Boxes /> <span>Inventory & Stock</span>
        </div>
        <div
          className={`nav ${activeTab === "products" ? "active" : ""}`}
          onClick={() => setActiveTab("products")}
          style={{ cursor: "pointer" }}
        >
          <FileText /> <span>Products Catalog</span>
        </div>
        <div
          className={`nav ${activeTab === "suppliers" ? "active" : ""}`}
          onClick={() => setActiveTab("suppliers")}
          style={{ cursor: "pointer" }}
        >
          <Truck /> <span>Suppliers</span>
        </div>
        <div
          className={`nav ${activeTab === "warehouses" ? "active" : ""}`}
          onClick={() => setActiveTab("warehouses")}
          style={{ cursor: "pointer" }}
        >
          <WarehouseIcon /> <span>Warehouses</span>
        </div>

        <p className="nav-label lower">INTELLIGENCE & AI</p>
        <div
          className={`nav ${activeTab === "risks" ? "active" : ""} ${canViewAnalytics ? "" : "disabled-nav"}`}
          onClick={() => canViewAnalytics && setActiveTab("risks")}
          style={{ cursor: canViewAnalytics ? "pointer" : "not-allowed" }}
        >
          <ShieldAlert /> <span>Risk intelligence</span>
          {canViewAnalytics ? (
            <em className="alert-count">{risks.length}</em>
          ) : (
            <em title="Requires Analyst or Manager role">Locked</em>
          )}
        </div>
        <div
          className={`nav ${activeTab === "approvals" ? "active" : ""}`}
          onClick={() => setActiveTab("approvals")}
          style={{ cursor: "pointer" }}
        >
          <CheckCircle2 /> <span>Decision Approvals</span>
          <em>{recs.length}</em>
        </div>
        <div
          className={`nav ${activeTab === "analytics" ? "active" : ""}`}
          onClick={() => setActiveTab("analytics")}
          style={{ cursor: "pointer" }}
        >
          <BrainCircuit /> <span>Operational AI Radar</span>
          <em className="badge-live-db" style={{ padding: "2px 5px", fontSize: 9 }}>Real ML</em>
        </div>


        <div className="sidebar-bottom">
          <div className="avatar">{userInitials}</div>
          <div className="user-label">
            <b>{currentUser.full_name}</b>
            <small>
              <span className={`role-badge ${currentUser.role}`}>{currentUser.role}</span>
            </small>
          </div>
          <button className="logout-btn" title="Sign out" onClick={() => void handleLogout()}>
            <LogOut size={16} />
          </button>
        </div>
      </aside>

      {/* Main Workspace Area */}
      <main className="main-content">
        <header className="topbar">
          <div className="breadcrumbs">
            Operations Tower <span>/</span>{" "}
            <b>
              {activeTab === "command-center" && "Executive Dashboard"}
              {activeTab === "orders" && "Customer & Purchase Orders"}
              {activeTab === "inventory" && "Warehouse Inventory & Movements"}
              {activeTab === "products" && "Product Catalog"}
              {activeTab === "suppliers" && "Supplier Directory"}
              {activeTab === "warehouses" && "Warehouse Facilities"}
              {activeTab === "risks" && "Operational Risk Radar"}
              {activeTab === "approvals" && "Human Decision Approvals & Safe Execution"}
              {activeTab === "analytics" && "Operational AI Radar & ML Baseline"}
            </b>
          </div>
          <div className="top-actions">
            <span className="system-status">
              <i /> Role: <b>{currentUser.role}</b>
            </span>
            <button
              className="icon-button"
              aria-label="Refresh"
              onClick={() => {
                if (activeTab === "command-center" || activeTab === "risks" || activeTab === "approvals" || activeTab === "analytics") {
                  void loadDashboard();
                } else if (activeTab === "suppliers") void loadSuppliers();
                else if (activeTab === "products") void loadProducts();
                else if (activeTab === "warehouses") void loadWarehouses();
                else if (activeTab === "inventory") void loadInventory();
                else if (activeTab === "orders") void loadOrders();
              }}

            >
              <RefreshCw size={16} className={loading || dashboardBusy ? "spin" : ""} />
            </button>
            <div className="top-avatar">{userInitials}</div>
          </div>
        </header>

        {/* Global Notifications */}
        {globalError && (
          <div className="error-banner" style={{ marginTop: 14 }}>
            <AlertTriangle size={15} /> <span>{globalError}</span>
            <button
              onClick={() => setGlobalError("")}
              style={{ marginLeft: "auto", background: "none", border: "none", cursor: "pointer" }}
            >
              <X size={14} />
            </button>
          </div>
        )}
        {globalSuccess && (
          <div className="success-banner" style={{ marginTop: 14 }}>
            <CheckCircle2 size={15} /> <span>{globalSuccess}</span>
            <button
              onClick={() => setGlobalSuccess("")}
              style={{ marginLeft: "auto", background: "none", border: "none", cursor: "pointer" }}
            >
              <X size={14} />
            </button>
          </div>
        )}

        {/* =========================================================================
            TAB 1: COMMAND CENTER (DASHBOARD)
           ========================================================================= */}
        {/* =========================================================================
            TAB 1: COMMAND CENTER (EXECUTIVE DASHBOARD)
           ========================================================================= */}
        {activeTab === "command-center" && (
          <div>
            <div className="page-heading">
              <div>
                <div className="eyebrow">
                  LIVE CONTROL TOWER <span className="heading-dot" /> REAL DATABASE INTELLIGENCE · PHASE 6
                </div>
                <h1>
                  Executive Control Tower<span>.</span>
                </h1>
                <p>
                  Authenticated as <b>{currentUser.email}</b> ({currentUser.role}) · Live server-side aggregations across operational tables
                </p>
              </div>
              <button
                className="refresh-button"
                onClick={() => void loadDashboard()}
                disabled={dashboardBusy}
                title="Re-aggregate metrics from database without modifying data"
              >
                <RefreshCw size={15} className={dashboardBusy ? "spin" : ""} />{" "}
                {dashboardBusy ? "Aggregating…" : "Refresh Intelligence"}
              </button>
            </div>

            {/* Executive Controls Bar: Source Mode & Date-Range Filter */}
            <div className="exec-controls-bar">
              <div className="exec-controls-left">
                {/* Data Source Mode Toggle */}
                <div className="source-toggle">
                  <button
                    className={`source-btn ${dataSourceMode === "live" ? "active live" : ""}`}
                    onClick={() => setDataSourceMode("live")}
                    title="Display authentic live operational database metrics"
                  >
                    <span className="source-dot" /> Real Database Records
                  </button>
                  <button
                    className={`source-btn ${dataSourceMode === "demo" ? "active demo" : ""}`}
                    onClick={() => setDataSourceMode("demo")}
                    title="Switch to illustrative benchmark demo snapshot"
                  >
                    <span className="source-dot" /> Illustrative Benchmark
                  </button>
                </div>

                {/* Date Range Selector */}
                {dataSourceMode === "live" && (
                  <div className="date-presets-group">
                    {[
                      { id: "7d", label: "Last 7 Days" },
                      { id: "30d", label: "Last 30 Days" },
                      { id: "90d", label: "Last 90 Days" },
                      { id: "all", label: "All Time" },
                      { id: "custom", label: "Custom Range" },
                    ].map((p) => (
                      <button
                        key={p.id}
                        className={`preset-chip ${dashboardRange === p.id ? "active" : ""}`}
                        onClick={() => {
                          setDashboardRange(p.id);
                          if (p.id !== "custom") {
                            void loadDashboard(p.id);
                          }
                        }}
                      >
                        {p.label}
                      </button>
                    ))}
                  </div>
                )}
              </div>

              {/* Custom Date Range Inputs */}
              {dataSourceMode === "live" && dashboardRange === "custom" && (
                <div className="custom-date-box">
                  <Calendar size={13} style={{ color: "#64748b" }} />
                  <input
                    type="date"
                    className="custom-date-input"
                    value={customStartDate}
                    onChange={(e) => setCustomStartDate(e.target.value)}
                    placeholder="Start date"
                  />
                  <span style={{ fontSize: 11, color: "#94a3b8" }}>to</span>
                  <input
                    type="date"
                    className="custom-date-input"
                    value={customEndDate}
                    onChange={(e) => setCustomEndDate(e.target.value)}
                    placeholder="End date"
                  />
                  <button
                    className="btn-primary btn-sm"
                    onClick={() => void loadDashboard("custom", customStartDate, customEndDate)}
                    disabled={dashboardBusy}
                  >
                    Apply Filter
                  </button>
                </div>
              )}
            </div>

            {/* Mode Banner / Warning */}
            {dataSourceMode === "demo" && (
              <div className="demo-alert-banner">
                <AlertTriangle size={16} />
                <div>
                  <b>ILLUSTRATIVE BENCHMARK MODE:</b> Displaying synthetically populated benchmark metrics for evaluation preview.
                  Switch to <b>Real Database Records</b> for authentic operational truth.
                </div>
              </div>
            )}

            {executiveError && (
              <div className="error-banner">
                <AlertTriangle size={16} />
                <span style={{ flex: 1 }}>{executiveError}</span>
                <button
                  className="btn-secondary btn-sm"
                  onClick={() => void loadDashboard()}
                  style={{ marginLeft: "auto" }}
                >
                  Retry
                </button>
              </div>
            )}

            {/* 6 Modern Executive KPI Cards */}
            <div className="kpi-grid-p6">
              {/* Card 1: Total Orders & Revenue */}
              <div className="kpi-card-p6">
                <div className="kpi-card-header">
                  <div className="kpi-icon blue">
                    <Package />
                  </div>
                  <span className="kpi-badge-tag info">Orders Volume</span>
                </div>
                <div>
                  <div className="kpi-label">Order Revenue & Pipeline</div>
                  <div className="kpi-main-number">
                    {dataSourceMode === "live"
                      ? `$${executiveData?.kpis.total_order_valuation ?? "0.00"}`
                      : "$18,420,000"}
                  </div>
                  <div className="kpi-subtext">
                    {dataSourceMode === "live"
                      ? `${executiveData?.kpis.total_orders ?? 0} Total Orders (${executiveData?.kpis.active_orders ?? 0} in progress)`
                      : "1,284 Orders Processed (Demo)"}
                  </div>
                </div>
                <div className="kpi-pills-row">
                  {dataSourceMode === "live" ? (
                    <>
                      <span className="mini-pill">Pending: {executiveData?.order_status_distribution.find((s) => s.status === "PENDING")?.count ?? 0}</span>
                      <span className="mini-pill">Proc: {executiveData?.order_status_distribution.find((s) => s.status === "PROCESSING")?.count ?? 0}</span>
                      <span className="mini-pill">Ship: {executiveData?.order_status_distribution.find((s) => s.status === "SHIPPED")?.count ?? 0}</span>
                      <span className="mini-pill" style={{ color: "#166534" }}>Deliv: {executiveData?.order_status_distribution.find((s) => s.status === "DELIVERED")?.count ?? 0}</span>
                    </>
                  ) : (
                    <span className="mini-pill">Active: 1,284 · Delayed: 37</span>
                  )}
                </div>
              </div>

              {/* Card 2: Inventory Valuation & Units */}
              <div className="kpi-card-p6">
                <div className="kpi-card-header">
                  <div className="kpi-icon violet">
                    <WarehouseIcon />
                  </div>
                  <span className="kpi-badge-tag info">Warehouse Assets</span>
                </div>
                <div>
                  <div className="kpi-label">Inventory Asset Valuation</div>
                  <div className="kpi-main-number" style={{ color: "#4f46e5" }}>
                    {dataSourceMode === "live"
                      ? `$${executiveData?.kpis.total_inventory_valuation ?? "0.00"}`
                      : "$18,420,000"}
                  </div>
                  <div className="kpi-subtext">
                    {dataSourceMode === "live"
                      ? `${(executiveData?.kpis.total_inventory_units ?? 0).toLocaleString()} Total Units on hand`
                      : "Cost-weighted warehouse assets"}
                  </div>
                </div>
                <div className="kpi-pills-row">
                  {dataSourceMode === "live" ? (
                    <>
                      <span className="mini-pill" style={{ color: "#166534" }}>
                        Available: {(executiveData?.kpis.available_inventory_units ?? 0).toLocaleString()}
                      </span>
                      <span className="mini-pill" style={{ color: "#b45309" }}>
                        Reserved: {(executiveData?.kpis.reserved_inventory_units ?? 0).toLocaleString()}
                      </span>
                    </>
                  ) : (
                    <span className="mini-pill">Available: 94.2%</span>
                  )}
                </div>
              </div>

              {/* Card 3: Inventory Health & Stockouts */}
              <div className="kpi-card-p6">
                <div className="kpi-card-header">
                  <div className="kpi-icon orange">
                    <AlertTriangle />
                  </div>
                  <span
                    className={`kpi-badge-tag ${
                      (executiveData?.kpis.stockout_items_count ?? 0) > 0
                        ? "danger"
                        : (executiveData?.kpis.low_stock_items_count ?? 0) > 0
                        ? "warning"
                        : "success"
                    }`}
                  >
                    {(executiveData?.kpis.stockout_items_count ?? 0) > 0
                      ? "Stockout Alert"
                      : (executiveData?.kpis.low_stock_items_count ?? 0) > 0
                      ? "Low Stock Risk"
                      : "Healthy Inventory"}
                  </span>
                </div>
                <div>
                  <div className="kpi-label">Stock Health & Thresholds</div>
                  <div
                    className="kpi-main-number"
                    style={{
                      color:
                        (executiveData?.kpis.stockout_items_count ?? 0) > 0
                          ? "#dc2626"
                          : (executiveData?.kpis.low_stock_items_count ?? 0) > 0
                          ? "#d97706"
                          : "#16a34a",
                    }}
                  >
                    {dataSourceMode === "live"
                      ? `${(executiveData?.kpis.stockout_items_count ?? 0) + (executiveData?.kpis.low_stock_items_count ?? 0)} SKUs`
                      : "12 Vulnerable SKUs"}
                  </div>
                  <div className="kpi-subtext">
                    {dataSourceMode === "live"
                      ? `${executiveData?.kpis.stockout_items_count ?? 0} in stockout · ${executiveData?.kpis.low_stock_items_count ?? 0} below reorder point`
                      : "Requires replenishment re-order"}
                  </div>
                </div>
                <div className="kpi-pills-row">
                  <span className="mini-pill" style={{ color: "#dc2626" }}>
                    Stockouts: {executiveData?.kpis.stockout_items_count ?? 0}
                  </span>
                  <span className="mini-pill" style={{ color: "#d97706" }}>
                    Reorder Triggered: {executiveData?.kpis.low_stock_items_count ?? 0}
                  </span>
                </div>
              </div>

              {/* Card 4: Decision Pipeline & Risk Radar */}
              <div className="kpi-card-p6">
                <div className="kpi-card-header">
                  <div className="kpi-icon red">
                    <ShieldAlert />
                  </div>
                  <span className="kpi-badge-tag danger">Decision Radar</span>
                </div>
                <div>
                  <div className="kpi-label">Pending Human Decisions</div>
                  <div className="kpi-main-number">
                    {dataSourceMode === "live"
                      ? executiveData?.kpis.pending_recommendations_count ?? 0
                      : recs.filter((r) => r.status === "PENDING").length}
                  </div>
                  <div className="kpi-subtext">
                    {dataSourceMode === "live"
                      ? `${executiveData?.kpis.critical_risks_count ?? 0} Critical operational risks active`
                      : "Awaiting manager approval sign-off"}
                  </div>
                </div>
                <div className="kpi-pills-row">
                  <button
                    className="text-link"
                    style={{ padding: 0, border: 0, marginTop: 0 }}
                    onClick={() => setActiveTab("approvals")}
                  >
                    Review Decisions & Approvals <ArrowUpRight size={12} style={{ verticalAlign: "middle" }} />
                  </button>
                </div>
              </div>

              {/* Card 5: Order Fulfilment Performance */}
              <div className="kpi-card-p6">
                <div className="kpi-card-header">
                  <div className="kpi-icon blue" style={{ background: "#ecfdf5", color: "#059669" }}>
                    <Truck />
                  </div>
                  <span className="kpi-badge-tag success">Fulfillment SLA</span>
                </div>
                <div>
                  <div className="kpi-label">On-Time Fulfillment Rate</div>
                  {dataSourceMode === "live" ? (
                    executiveData?.fulfillment_summary.has_sufficient_data &&
                    executiveData.fulfillment_summary.on_time_rate !== null ? (
                      <>
                        <div className="kpi-main-number" style={{ color: "#059669" }}>
                          {executiveData.fulfillment_summary.on_time_rate}%
                        </div>
                        <div className="kpi-subtext">
                          Avg Cycle: {executiveData.fulfillment_summary.average_fulfillment_days ?? "—"} days ({executiveData.fulfillment_summary.total_delivered_orders} delivered)
                        </div>
                      </>
                    ) : (
                      <div className="insufficient-data-box" style={{ marginTop: 4 }}>
                        <b><Info size={13} /> Insufficient Delivery Data</b>
                        <span>{executiveData?.fulfillment_summary.status_message || "Requires completed orders with recorded delivery targets to calculate on-time percentage."}</span>
                      </div>
                    )
                  ) : (
                    <>
                      <div className="kpi-main-number" style={{ color: "#059669" }}>98.2%</div>
                      <div className="kpi-subtext">Simulated Benchmark (Demo)</div>
                    </>
                  )}
                </div>
                <div className="kpi-pills-row">
                  <span className="mini-pill">
                    Delivered: {executiveData?.kpis.delivered_orders ?? 0} Orders
                  </span>
                </div>
              </div>

              {/* Card 6: Supplier Ecosystem Performance */}
              <div className="kpi-card-p6">
                <div className="kpi-card-header">
                  <div className="kpi-icon violet" style={{ background: "#f0fdf4", color: "#16a34a" }}>
                    <Factory />
                  </div>
                  <span className="kpi-badge-tag info">Vendor Reliability</span>
                </div>
                <div>
                  <div className="kpi-label">Supplier Ecosystem Reliability</div>
                  {dataSourceMode === "live" ? (
                    executiveData?.supplier_summary.has_sufficient_data &&
                    executiveData.supplier_summary.average_reliability_score !== null ? (
                      <>
                        <div className="kpi-main-number" style={{ color: "#2563eb" }}>
                          {((executiveData.kpis.average_supplier_reliability || 0) * 100).toFixed(1)}%
                        </div>
                        <div className="kpi-subtext">
                          {executiveData.supplier_summary.total_suppliers} Active Registered Vendors (Avg Lead Time: {executiveData.supplier_summary.average_lead_time_days ?? 7}d)
                        </div>
                      </>
                    ) : (
                      <div className="insufficient-data-box" style={{ marginTop: 4 }}>
                        <b><Info size={13} /> No Active Vendors</b>
                        <span>{executiveData?.supplier_summary.transparency_note || "No active suppliers recorded in the catalog."}</span>
                      </div>
                    )
                  ) : (
                    <>
                      <div className="kpi-main-number" style={{ color: "#2563eb" }}>95.0%</div>
                      <div className="kpi-subtext">Simulated Vendor Benchmark (Demo)</div>
                    </>
                  )}
                </div>
                <div className="kpi-pills-row">
                  <button
                    className="text-link"
                    style={{ padding: 0, border: 0, marginTop: 0 }}
                    onClick={() => setActiveTab("suppliers")}
                  >
                    View Supplier Master <ArrowUpRight size={12} style={{ verticalAlign: "middle" }} />
                  </button>
                </div>
              </div>
            </div>

            {/* Primary Visual Analytics Grid: Orders Over Time & Status Breakdown */}
            <div className="exec-visual-grid">
              {/* Left Panel: Order Volume Time Series */}
              <div className="panel">
                <div className="panel-heading">
                  <div>
                    <h2>Order Volume & Dispatch Trends Over Time</h2>
                    <p>
                      {dataSourceMode === "live"
                        ? `Historical order activity for: ${executiveData?.date_range.label || "Last 30 Days"}`
                        : "Weekly comparison of completed orders vs delayed dispatches (Demo Benchmark)"}
                    </p>
                  </div>
                  <span className="select-chip">
                    {dataSourceMode === "live"
                      ? executiveData?.date_range.label || "Last 30 Days"
                      : "Illustrative Demo"}
                  </span>
                </div>

                <div className="chart-legend">
                  <span>
                    <i className="legend-orders" /> Completed Orders
                  </span>
                  <span>
                    <i className="legend-late" /> Delayed Orders
                  </span>
                </div>

                {/* Render Chart: Live or Demo */}
                {dataSourceMode === "live" ? (
                  executiveData?.order_volume_trend && executiveData.order_volume_trend.length > 0 ? (
                    (() => {
                      const trend = executiveData.order_volume_trend;
                      const maxOrders = Math.max(...trend.map((t) => t.orders_count || 0), 5);
                      const yMax = Math.ceil(maxOrders / 5) * 5 || 10;
                      const yMidHigh = Math.round(yMax * 0.67);
                      const yMidLow = Math.round(yMax * 0.33);

                      return (
                        <div className="chart-area">
                          <div className="y-labels">
                            <span>{yMax}</span>
                            <span>{yMidHigh}</span>
                            <span>{yMidLow}</span>
                            <span>0</span>
                          </div>
                          <div className="chart-content">
                            <div className="grid-lines">
                              <i />
                              <i />
                              <i />
                              <i />
                            </div>
                            <div className="bar-chart">
                              {trend.map((t, idx) => {
                                const ordersHeight = Math.min(130, Math.max(6, Math.round((t.orders_count / yMax) * 130)));
                                const lateHeight = Math.min(130, Math.max(0, Math.round((t.delayed_count / yMax) * 130)));
                                return (
                                  <div
                                    key={idx}
                                    className="bar-group"
                                    title={`${t.date}: ${t.orders_count} orders, ${t.delayed_count} delayed, Revenue: $${t.total_revenue}`}
                                  >
                                    <div className="bar-pair">
                                      <div
                                        className="orders-bar"
                                        style={{ height: `${ordersHeight}px` }}
                                        title={`Orders: ${t.orders_count}`}
                                      />
                                      {t.delayed_count > 0 && (
                                        <div
                                          className="late-bar"
                                          style={{ height: `${lateHeight}px` }}
                                          title={`Delayed: ${t.delayed_count}`}
                                        />
                                      )}
                                    </div>
                                    <small>{t.date.slice(5)}</small>
                                  </div>
                                );
                              })}
                            </div>
                          </div>
                        </div>
                      );
                    })()
                  ) : (
                    <div className="empty-widget-box">
                      <Package size={28} />
                      <b>No Order Volume Recorded in Selected Window</b>
                      <p>
                        No order records found between {executiveData?.date_range.label || "the selected dates"}.
                        Create a customer order in the Orders tab or widen the date filter.
                      </p>
                    </div>
                  )
                ) : (
                  (() => {
                    const trendData = data?.trend || [];
                    const maxOrders = Math.max(...trendData.map((t) => t.orders || 0), 100);
                    const yMax = Math.ceil(maxOrders / 200) * 200 || 1400;
                    const yMidHigh = Math.round(yMax * 0.67);
                    const yMidLow = Math.round(yMax * 0.33);

                    return (
                      <div className="chart-area">
                        <div className="y-labels">
                          <span>{yMax.toLocaleString()}</span>
                          <span>{yMidHigh.toLocaleString()}</span>
                          <span>{yMidLow.toLocaleString()}</span>
                          <span>0</span>
                        </div>
                        <div className="chart-content">
                          <div className="grid-lines">
                            <i />
                            <i />
                            <i />
                            <i />
                          </div>
                          <div className="bar-chart">
                            {trendData.map((t, idx) => {
                              const ordersHeight = Math.min(130, Math.max(4, Math.round((t.orders / yMax) * 130)));
                              const lateHeight = Math.min(130, Math.max(4, Math.round((t.late / yMax) * 130 * 4)));
                              return (
                                <div key={idx} className="bar-group" title={`${t.day}: ${t.orders} completed, ${t.late} delayed`}>
                                  <div className="bar-pair">
                                    <div
                                      className="orders-bar"
                                      style={{ height: `${ordersHeight}px` }}
                                      title={`Completed: ${t.orders}`}
                                    />
                                    <div
                                      className="late-bar"
                                      style={{ height: `${lateHeight}px` }}
                                      title={`Delayed: ${t.late}`}
                                    />
                                  </div>
                                  <small>{t.day}</small>
                                </div>
                              );
                            })}
                          </div>
                        </div>
                      </div>
                    );
                  })()
                )}

                <div className="chart-foot">
                  <span>
                    <i></i> Total Revenue: <b>${executiveData?.kpis.total_order_valuation || "0.00"}</b>
                  </span>
                  <span>Average Order: ${executiveData?.order_volume_trend && executiveData.order_volume_trend.length > 0 ? (Number(executiveData.kpis.total_order_valuation) / Math.max(1, executiveData.kpis.total_orders)).toFixed(2) : "0.00"}</span>
                </div>
              </div>

              {/* Right Panel: Order Status Breakdown Distribution */}
              <div className="panel">
                <div className="panel-heading">
                  <div>
                    <h2>Order Lifecycle Distribution</h2>
                    <p>Status breakdown across active pipeline</p>
                  </div>
                  <span className="count-pill">
                    {executiveData?.kpis.total_orders ?? 0} Orders
                  </span>
                </div>

                {/* Progress bar */}
                <div className="status-bar-container">
                  {executiveData?.order_status_distribution.map((item) => (
                    item.percentage > 0 && (
                      <div
                        key={item.status}
                        className={`status-segment ${item.status}`}
                        style={{ width: `${item.percentage}%` }}
                        title={`${item.status}: ${item.count} (${item.percentage}%)`}
                      />
                    )
                  ))}
                </div>

                {/* Status Breakdown Table List */}
                <div className="status-breakdown-list">
                  {executiveData?.order_status_distribution.map((item) => (
                    <div key={item.status} className="status-breakdown-row">
                      <div style={{ display: "flex", alignItems: "center" }}>
                        <span
                          className="status-color-dot"
                          style={{
                            background:
                              item.status === "PENDING"
                                ? "#f59e0b"
                                : item.status === "PROCESSING"
                                ? "#6366f1"
                                : item.status === "SHIPPED"
                                ? "#3b82f6"
                                : item.status === "DELIVERED"
                                ? "#10b981"
                                : "#ef4444",
                          }}
                        />
                        <span className={`status-badge badge-${item.status.toLowerCase()}`}>
                          {item.status}
                        </span>
                      </div>
                      <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
                        <span style={{ fontWeight: 700, color: "#1e293b" }}>{item.count}</span>
                        <span style={{ color: "#64748b", minWidth: 40, textAlign: "right" }}>{item.percentage}%</span>
                        <span style={{ fontWeight: 600, color: "#475569", minWidth: 70, textAlign: "right" }}>${item.total_amount}</span>
                      </div>
                    </div>
                  ))}

                  {(!executiveData || executiveData.kpis.total_orders === 0) && (
                    <div className="empty">No order status records in this period.</div>
                  )}
                </div>
              </div>
            </div>

            {/* Secondary Visual Analytics Grid: Multi-Facility Warehouse Valuation & Categories */}
            <div className="exec-visual-grid" style={{ marginTop: 14 }}>
              {/* Left Panel: Warehouse Facilities */}
              <div className="panel">
                <div className="panel-heading">
                  <div>
                    <h2>Multi-Facility Warehouse Valuation & Capacity</h2>
                    <p>Asset distribution and utilization across distribution centers</p>
                  </div>
                  <span className="select-chip">
                    {executiveData?.warehouse_stock.length ?? 0} Facilities
                  </span>
                </div>

                <div className="facility-card-grid" style={{ marginTop: 14 }}>
                  {executiveData?.warehouse_stock.map((w) => {
                    return (
                      <div key={w.warehouse_id} className="facility-stat-card">
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                          <div>
                            <b style={{ fontSize: 13, color: "#0f172a" }}>{w.warehouse_name}</b>
                            <div style={{ fontSize: 10, color: "#64748b" }}>Code: {w.warehouse_code} · {w.sku_count} Active SKUs</div>
                          </div>
                          <span className="badge-live-db" style={{ fontSize: 10 }}>
                            ${w.valuation}
                          </span>
                        </div>

                        <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: "#475569" }}>
                          <span>On Hand: <b>{w.total_units}</b></span>
                          <span>Avail: <b style={{ color: "#166534" }}>{w.available_units}</b></span>
                          <span>Reserved: <b style={{ color: "#b45309" }}>{w.reserved_units}</b></span>
                        </div>
                      </div>
                    );
                  })}

                  {(!executiveData?.warehouse_stock || executiveData.warehouse_stock.length === 0) && (
                    <div className="empty">No inventory facilities recorded.</div>
                  )}
                </div>
              </div>

              {/* Right Panel: Product Category Asset Breakdown */}
              <div className="panel">
                <div className="panel-heading">
                  <div>
                    <h2>Inventory by Product Category</h2>
                    <p>Catalog asset value and units weighting</p>
                  </div>
                  <span className="count-pill">
                    {executiveData?.category_stock.length ?? 0} Categories
                  </span>
                </div>

                <div style={{ display: "flex", flexDirection: "column", gap: 10, marginTop: 14 }}>
                  {executiveData?.category_stock.map((c) => (
                    <div
                      key={c.category}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        padding: "10px 12px",
                        background: "#f8fafc",
                        borderRadius: 8,
                        fontSize: 12,
                      }}
                    >
                      <div>
                        <b style={{ color: "#0f172a" }}>{c.category}</b>
                        <div style={{ fontSize: 10, color: "#64748b" }}>
                          {c.sku_count} SKUs · {c.total_units} Total Units
                        </div>
                      </div>
                      <span style={{ fontWeight: 700, color: "#4f46e5" }}>
                        ${c.valuation}
                      </span>
                    </div>
                  ))}

                  {(!executiveData?.category_stock || executiveData.category_stock.length === 0) && (
                    <div className="empty">No catalog categories recorded.</div>
                  )}
                </div>
              </div>
            </div>

            {/* Low-Stock and Stockout Vulnerability Table */}
            <div className="panel" style={{ marginTop: 14 }}>
              <div className="panel-heading">
                <div>
                  <h2>Stockout & Low-Stock Vulnerability Alerts</h2>
                  <p>Inventory balances currently at or below reorder threshold</p>
                </div>
                <span
                  className={`count-pill ${
                    (executiveData?.low_stock_alerts.length ?? 0) > 0 ? "" : "badge-delivered"
                  }`}
                  style={{
                    background: (executiveData?.low_stock_alerts.length ?? 0) > 0 ? "#fef2f2" : "#ecfdf5",
                    color: (executiveData?.low_stock_alerts.length ?? 0) > 0 ? "#b91c1c" : "#047857",
                  }}
                >
                  {executiveData?.low_stock_alerts.length ?? 0} Items At Risk
                </span>
              </div>

              {executiveData?.low_stock_alerts && executiveData.low_stock_alerts.length > 0 ? (
                <div className="ops-table-container" style={{ marginTop: 12, border: "none", boxShadow: "none" }}>
                  <table className="ops-table">
                    <thead>
                      <tr>
                        <th>Product SKU & Name</th>
                        <th>Category</th>
                        <th>Facility</th>
                        <th>On Hand</th>
                        <th>Reserved</th>
                        <th>Available</th>
                        <th>Reorder Point</th>
                        <th>Safety Stock</th>
                        <th>Status</th>
                        <th>Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {executiveData.low_stock_alerts.map((item) => (
                        <tr key={item.inventory_id}>
                          <td>
                            <b>{item.product_name}</b>
                            <div style={{ fontSize: 10, color: "#64748b" }}>{item.product_sku}</div>
                          </td>
                          <td>{item.product_category}</td>
                          <td>
                            <b>{item.warehouse_code}</b>
                            <div style={{ fontSize: 10, color: "#64748b" }}>{item.warehouse_name}</div>
                          </td>
                          <td>{item.quantity_on_hand}</td>
                          <td>{item.quantity_reserved}</td>
                          <td>
                            <b style={{ color: item.available_quantity <= 0 ? "#dc2626" : "#d97706" }}>
                              {item.available_quantity}
                            </b>
                          </td>
                          <td>{item.reorder_quantity}</td>
                          <td>{item.safety_stock}</td>
                          <td>
                            <span
                              className={`status-badge ${
                                item.status === "STOCKOUT" ? "badge-cancelled" : "badge-pending"
                              }`}
                            >
                              {item.status}
                            </span>
                          </td>
                          <td>
                            <button
                              className="btn-secondary btn-sm"
                              onClick={() => {
                                setActiveTab("inventory");
                              }}
                            >
                              Manage Stock
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="empty-widget-box">
                  <CheckCircle2 size={24} style={{ color: "#16a34a" }} />
                  <b style={{ color: "#166534" }}>All Inventory Levels Healthy</b>
                  <p>All stored product balances are currently operating above their configured reorder quantities.</p>
                </div>
              )}
            </div>

            {/* Active Risks & Pending Approvals Previews */}
            <div className="primary-grid" style={{ marginTop: 14 }}>
              {/* Critical Risks Preview */}
              <div className="panel risk-panel">
                <div className="panel-heading">
                  <div>
                    <h2>Live Risk Intelligence Signals</h2>
                    <p>Explainable operational risks detected across warehouse and orders</p>
                  </div>
                  <button
                    className="text-link"
                    style={{ padding: 0, border: 0, width: "auto" }}
                    onClick={() => setActiveTab("risks")}
                  >
                    View All Radar ({risks.length}) <ArrowUpRight size={12} style={{ verticalAlign: "middle" }} />
                  </button>
                </div>
                <div className="risk-list">
                  {risks.slice(0, 3).map((r) => (
                    <div key={r.id} className="risk-row">
                      <div className={`risk-symbol ${r.severity.toLowerCase()}`}>
                        <AlertTriangle size={15} />
                      </div>
                      <div className="risk-copy">
                        <div className="risk-title">
                          <span>{r.entity_name || r.supplier || r.id}</span>
                          <span className={`severity ${r.severity.toLowerCase()}`}>{r.severity}</span>
                        </div>
                        <p>{r.explanation || r.message}</p>
                      </div>
                      <div className="risk-score">
                        <b>{r.score}</b>
                        <small>Risk Index</small>
                      </div>
                    </div>
                  ))}
                  {risks.length === 0 && (
                    <div className="empty">No critical risks flagged in this period.</div>
                  )}
                </div>
              </div>

              {/* Pending Recommendations Preview */}
              <div className="panel">
                <div className="panel-heading">
                  <div>
                    <h2>Decision Pipeline & Approvals</h2>
                    <p>Proposals awaiting human review and signed execution</p>
                  </div>
                  <button
                    className="text-link"
                    style={{ padding: 0, border: 0, width: "auto" }}
                    onClick={() => setActiveTab("approvals")}
                  >
                    Open Approvals ({recs.filter((r) => r.status === "PENDING").length}) <ArrowUpRight size={12} style={{ verticalAlign: "middle" }} />
                  </button>
                </div>

                <div style={{ display: "flex", flexDirection: "column", gap: 10, marginTop: 14 }}>
                  {recs
                    .filter((r) => r.status === "PENDING")
                    .slice(0, 3)
                    .map((rec) => (
                      <div
                        key={rec.id}
                        style={{
                          padding: "12px",
                          background: "#f8fafc",
                          borderRadius: 8,
                          border: "1px solid #e2e8f0",
                          fontSize: 12,
                        }}
                      >
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                          <b style={{ color: "#0f172a" }}>{rec.title}</b>
                          <span className="status-badge badge-pending">PENDING</span>
                        </div>
                        <p style={{ margin: "4px 0", fontSize: 11, color: "#64748b" }}>
                          Entity: <b>{rec.entity_name}</b> · Action: <code>{rec.proposed_action || rec.action}</code>
                        </p>
                      </div>
                    ))}

                  {recs.filter((r) => r.status === "PENDING").length === 0 && (
                    <div className="empty">No recommendations awaiting sign-off.</div>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* =========================================================================
            TAB 2: SUPPLIERS DIRECTORY
           ========================================================================= */}
        {activeTab === "suppliers" && (
          <div className="view-container">
            <div className="page-heading" style={{ paddingBottom: 16 }}>
              <div>
                <div className="eyebrow">
                  PHASE 4 · VENDOR MANAGEMENT <span className="heading-dot" /> POSTGRESQL / SQLITE
                </div>
                <h1>
                  Suppliers directory<span>.</span>
                </h1>
                <p>
                  Real database records tracking vendor reliability scores, lead times, and catalog links.
                </p>
              </div>
              <div>
                <button
                  className={canManageData ? "btn-primary" : "btn-secondary disabled-lock-btn"}
                  onClick={() => canManageData && setSupplierModal(true)}
                  disabled={!canManageData}
                  title={canManageData ? "Create Supplier" : "Requires Operations Manager or Admin role"}
                >
                  {canManageData ? <Plus size={15} /> : <Lock size={14} />} New Supplier
                </button>
              </div>
            </div>

            {/* Toolbar */}
            <div className="toolbar">
              <div className="toolbar-left">
                <div style={{ position: "relative" }}>
                  <input
                    type="text"
                    className="search-input"
                    placeholder="Search by code or supplier name…"
                    value={supplierSearch}
                    onChange={(e) => setSupplierSearch(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && void loadSuppliers()}
                  />
                </div>
                <button className="btn-secondary btn-sm" onClick={() => void loadSuppliers()}>
                  <Search size={13} /> Filter
                </button>
              </div>
              <div className="toolbar-right">
                <span className="badge-live-db">
                  <Database size={11} /> Live Database Entity
                </span>
              </div>
            </div>

            {/* Table */}
            <div className="ops-table-container">
              <table className="ops-table">
                <thead>
                  <tr>
                    <th>Code</th>
                    <th>Supplier Name</th>
                    <th>Email Contact</th>
                    <th>Phone</th>
                    <th>Lead Time</th>
                    <th>Reliability</th>
                    <th>Status</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {suppliers.map((s) => (
                    <tr key={s.id}>
                      <td>
                        <b>{s.code}</b>
                      </td>
                      <td>{s.name}</td>
                      <td>{s.contact_email || "—"}</td>
                      <td>{s.contact_phone || "—"}</td>
                      <td>{s.lead_time_days} days</td>
                      <td>
                        <span style={{ fontWeight: 700, color: Number(s.reliability_score) >= 0.9 ? "#16a34a" : "#ca8a04" }}>
                          {(Number(s.reliability_score) * 100).toFixed(0)}%
                        </span>
                      </td>
                      <td>
                        <span className={`status-badge ${s.is_active ? "badge-active" : "badge-inactive"}`}>
                          {s.is_active ? "Active" : "Inactive"}
                        </span>
                      </td>
                      <td>
                        {s.is_active && (
                          <button
                            className={canManageData ? "btn-secondary btn-sm" : "btn-secondary btn-sm disabled-lock-btn"}
                            onClick={() => canManageData && void handleDeactivateSupplier(s.id)}
                            disabled={!canManageData}
                            title={canManageData ? "Deactivate" : "Requires Operations Manager"}
                          >
                            Deactivate
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                  {suppliers.length === 0 && (
                    <tr>
                      <td colSpan={8} style={{ textAlign: "center", padding: 36, color: "#94a3b8" }}>
                        No suppliers found. Click "+ New Supplier" to add a vendor.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>

              <div className="pagination-bar">
                <span>
                  Showing {suppliers.length} of {supplierTotal} suppliers
                </span>
                <div className="pagination-controls">
                  <button
                    className="page-btn"
                    disabled={supplierPage <= 1}
                    onClick={() => setSupplierPage((p) => Math.max(1, p - 1))}
                  >
                    Previous
                  </button>
                  <span>Page {supplierPage}</span>
                  <button
                    className="page-btn"
                    disabled={suppliers.length < 15}
                    onClick={() => setSupplierPage((p) => p + 1)}
                  >
                    Next
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* =========================================================================
            TAB 3: PRODUCTS CATALOG
           ========================================================================= */}
        {activeTab === "products" && (
          <div className="view-container">
            <div className="page-heading" style={{ paddingBottom: 16 }}>
              <div>
                <div className="eyebrow">
                  PHASE 4 · CATALOG & PRICING <span className="heading-dot" /> DECIMAL PRECISION
                </div>
                <h1>
                  Product catalog<span>.</span>
                </h1>
                <p>
                  Maintain catalog items, SKUs, backend cost/pricing safeguards, and reorder levels.
                </p>
              </div>
              <div>
                <button
                  className={canManageData ? "btn-primary" : "btn-secondary disabled-lock-btn"}
                  onClick={() => canManageData && setProductModal(true)}
                  disabled={!canManageData}
                  title={canManageData ? "Add Product" : "Requires Operations Manager or Admin role"}
                >
                  {canManageData ? <Plus size={15} /> : <Lock size={14} />} New Product
                </button>
              </div>
            </div>

            {/* Toolbar */}
            <div className="toolbar">
              <div className="toolbar-left">
                <input
                  type="text"
                  className="search-input"
                  placeholder="Search SKU, name, category…"
                  value={productSearch}
                  onChange={(e) => setProductSearch(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && void loadProducts()}
                />
                <button className="btn-secondary btn-sm" onClick={() => void loadProducts()}>
                  <Search size={13} /> Filter
                </button>
              </div>
              <div className="toolbar-right">
                <span className="badge-live-db">
                  <Database size={11} /> Live Database Entity
                </span>
              </div>
            </div>

            {/* Table */}
            <div className="ops-table-container">
              <table className="ops-table">
                <thead>
                  <tr>
                    <th>SKU</th>
                    <th>Product Name</th>
                    <th>Category</th>
                    <th>Supplier</th>
                    <th>Unit Price</th>
                    <th>Unit Cost</th>
                    <th>Reorder Lvl</th>
                    <th>Status</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {products.map((p) => (
                    <tr key={p.id}>
                      <td>
                        <code>{p.sku}</code>
                      </td>
                      <td>
                        <b>{p.name}</b>
                      </td>
                      <td>{p.category}</td>
                      <td>{p.supplier_name || "—"}</td>
                      <td>
                        <b>${Number(p.unit_price).toFixed(2)}</b>
                      </td>
                      <td>${Number(p.unit_cost).toFixed(2)}</td>
                      <td>{p.reorder_point} units</td>
                      <td>
                        <span className={`status-badge ${p.is_active ? "badge-active" : "badge-inactive"}`}>
                          {p.is_active ? "Active" : "Inactive"}
                        </span>
                      </td>
                      <td>
                        {p.is_active && (
                          <button
                            className={canManageData ? "btn-secondary btn-sm" : "btn-secondary btn-sm disabled-lock-btn"}
                            onClick={() => canManageData && void handleDeactivateProduct(p.id)}
                            disabled={!canManageData}
                            title={canManageData ? "Deactivate" : "Requires Operations Manager"}
                          >
                            Deactivate
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                  {products.length === 0 && (
                    <tr>
                      <td colSpan={9} style={{ textAlign: "center", padding: 36, color: "#94a3b8" }}>
                        No products found. Click "+ New Product" to add a catalog entry.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>

              <div className="pagination-bar">
                <span>
                  Showing {products.length} of {productTotal} products
                </span>
                <div className="pagination-controls">
                  <button
                    className="page-btn"
                    disabled={productPage <= 1}
                    onClick={() => setProductPage((p) => Math.max(1, p - 1))}
                  >
                    Previous
                  </button>
                  <span>Page {productPage}</span>
                  <button
                    className="page-btn"
                    disabled={products.length < 15}
                    onClick={() => setProductPage((p) => p + 1)}
                  >
                    Next
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* =========================================================================
            TAB 4: WAREHOUSES FACILITIES
           ========================================================================= */}
        {activeTab === "warehouses" && (
          <div className="view-container">
            <div className="page-heading" style={{ paddingBottom: 16 }}>
              <div>
                <div className="eyebrow">
                  PHASE 4 · LOGISTICS NETWORK <span className="heading-dot" /> FULFILLMENT NODES
                </div>
                <h1>
                  Warehouse facilities<span>.</span>
                </h1>
                <p>
                  Manage storage facilities, geographic nodes, and capacity limits.
                </p>
              </div>
              <div>
                <button
                  className={canManageData ? "btn-primary" : "btn-secondary disabled-lock-btn"}
                  onClick={() => canManageData && setWarehouseModal(true)}
                  disabled={!canManageData}
                  title={canManageData ? "Add Warehouse" : "Requires Operations Manager or Admin role"}
                >
                  {canManageData ? <Plus size={15} /> : <Lock size={14} />} New Warehouse
                </button>
              </div>
            </div>

            {/* Toolbar */}
            <div className="toolbar">
              <div className="toolbar-left">
                <input
                  type="text"
                  className="search-input"
                  placeholder="Search code, name, location…"
                  value={warehouseSearch}
                  onChange={(e) => setWarehouseSearch(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && void loadWarehouses()}
                />
                <button className="btn-secondary btn-sm" onClick={() => void loadWarehouses()}>
                  <Search size={13} /> Filter
                </button>
              </div>
              <div className="toolbar-right">
                <span className="badge-live-db">
                  <Database size={11} /> Live Database Entity
                </span>
              </div>
            </div>

            {/* Table */}
            <div className="ops-table-container">
              <table className="ops-table">
                <thead>
                  <tr>
                    <th>Facility Code</th>
                    <th>Warehouse Name</th>
                    <th>Location</th>
                    <th>Max Capacity</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {warehouses.map((w) => (
                    <tr key={w.id}>
                      <td>
                        <b>{w.code}</b>
                      </td>
                      <td>{w.name}</td>
                      <td>{w.location}</td>
                      <td>{w.capacity.toLocaleString()} units</td>
                      <td>
                        <span className={`status-badge ${w.is_active ? "badge-active" : "badge-inactive"}`}>
                          {w.is_active ? "Active" : "Inactive"}
                        </span>
                      </td>
                    </tr>
                  ))}
                  {warehouses.length === 0 && (
                    <tr>
                      <td colSpan={5} style={{ textAlign: "center", padding: 36, color: "#94a3b8" }}>
                        No warehouses registered. Click "+ New Warehouse" to add a facility.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>

              <div className="pagination-bar">
                <span>
                  Showing {warehouses.length} of {warehouseTotal} warehouses
                </span>
                <div className="pagination-controls">
                  <button
                    className="page-btn"
                    disabled={warehousePage <= 1}
                    onClick={() => setWarehousePage((p) => Math.max(1, p - 1))}
                  >
                    Previous
                  </button>
                  <span>Page {warehousePage}</span>
                  <button
                    className="page-btn"
                    disabled={warehouses.length < 15}
                    onClick={() => setWarehousePage((p) => p + 1)}
                  >
                    Next
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* =========================================================================
            TAB 5: INVENTORY & STOCK MOVEMENTS
           ========================================================================= */}
        {activeTab === "inventory" && (
          <div className="view-container">
            <div className="page-heading" style={{ paddingBottom: 16 }}>
              <div>
                <div className="eyebrow">
                  PHASE 4 · STOCK CONTROLS <span className="heading-dot" /> ATOMIC CONCURRENCY & MOVEMENTS
                </div>
                <h1>
                  Inventory & stock movements<span>.</span>
                </h1>
                <p>
                  Controlled receipts and issues enforcing invariant <code>quantity_reserved &le; on_hand</code> with locking.
                </p>
              </div>
              <div style={{ display: "flex", gap: 8 }}>
                <button
                  className={canManageData ? "btn-primary" : "btn-secondary disabled-lock-btn"}
                  onClick={() => canManageData && setReceiptModal(true)}
                  disabled={!canManageData}
                  title={canManageData ? "Receive Stock" : "Requires Operations Manager"}
                >
                  {canManageData ? <Plus size={15} /> : <Lock size={14} />} Receive Stock (PO)
                </button>
                <button
                  className={canManageData ? "btn-secondary" : "btn-secondary disabled-lock-btn"}
                  onClick={() => canManageData && setIssueModal(true)}
                  disabled={!canManageData}
                  title={canManageData ? "Issue Stock" : "Requires Operations Manager"}
                >
                  {canManageData ? <Truck size={15} /> : <Lock size={14} />} Issue Stock (Dispatch)
                </button>
              </div>
            </div>

            {/* Sub-tab selection */}
            <div className="subtab-bar">
              <button
                className={`subtab-btn ${inventorySubTab === "balances" ? "active" : ""}`}
                onClick={() => setInventorySubTab("balances")}
              >
                Stock Balances
              </button>
              <button
                className={`subtab-btn ${inventorySubTab === "movements" ? "active" : ""}`}
                onClick={() => setInventorySubTab("movements")}
              >
                Movement Audit History
              </button>
            </div>

            {/* Balances Sub-tab */}
            {inventorySubTab === "balances" && (
              <>
                <div className="toolbar">
                  <div className="toolbar-left">
                    <input
                      type="text"
                      className="search-input"
                      placeholder="Search product SKU, name, warehouse…"
                      value={inventorySearch}
                      onChange={(e) => setInventorySearch(e.target.value)}
                      onKeyDown={(e) => e.key === "Enter" && void loadInventory()}
                    />
                    <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, color: "#475569" }}>
                      <input
                        type="checkbox"
                        checked={lowStockFilter}
                        onChange={(e) => setLowStockFilter(e.target.checked)}
                      />
                      Low Stock Only
                    </label>
                    <button className="btn-secondary btn-sm" onClick={() => void loadInventory()}>
                      <Search size={13} /> Filter
                    </button>
                  </div>
                  <div className="toolbar-right">
                    <span className="badge-live-db">
                      <Database size={11} /> Live Balances
                    </span>
                  </div>
                </div>

                <div className="ops-table-container">
                  <table className="ops-table">
                    <thead>
                      <tr>
                        <th>Product SKU</th>
                        <th>Product Name</th>
                        <th>Warehouse</th>
                        <th>On Hand</th>
                        <th>Reserved</th>
                        <th>Available Stock</th>
                        <th>Reorder Level</th>
                        <th>Stock Health</th>
                      </tr>
                    </thead>
                    <tbody>
                      {inventoryItems.map((inv) => {
                        const isLow = inv.available_quantity <= inv.reorder_quantity;
                        return (
                          <tr key={inv.id}>
                            <td>
                              <code>{inv.product_sku || "—"}</code>
                            </td>
                            <td>
                              <b>{inv.product_name || "—"}</b>
                            </td>
                            <td>
                              <b>{inv.warehouse_code}</b> ({inv.warehouse_name})
                            </td>
                            <td>{inv.quantity_on_hand}</td>
                            <td>{inv.quantity_reserved}</td>
                            <td>
                              <b style={{ color: isLow ? "#dc2626" : "#16a34a" }}>
                                {inv.available_quantity}
                              </b>
                            </td>
                            <td>{inv.reorder_quantity}</td>
                            <td>
                              <span className={`status-badge ${isLow ? "badge-cancelled" : "badge-active"}`}>
                                {isLow ? "Low Stock Trigger" : "Healthy"}
                              </span>
                            </td>
                          </tr>
                        );
                      })}
                      {inventoryItems.length === 0 && (
                        <tr>
                          <td colSpan={8} style={{ textAlign: "center", padding: 36, color: "#94a3b8" }}>
                            No inventory records found. Use "Receive Stock" to record initial inventory balances.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>

                  <div className="pagination-bar">
                    <span>
                      Showing {inventoryItems.length} of {inventoryTotal} inventory rows
                    </span>
                    <div className="pagination-controls">
                      <button
                        className="page-btn"
                        disabled={inventoryPage <= 1}
                        onClick={() => setInventoryPage((p) => Math.max(1, p - 1))}
                      >
                        Previous
                      </button>
                      <span>Page {inventoryPage}</span>
                      <button
                        className="page-btn"
                        disabled={inventoryItems.length < 15}
                        onClick={() => setInventoryPage((p) => p + 1)}
                      >
                        Next
                      </button>
                    </div>
                  </div>
                </div>
              </>
            )}

            {/* Movements Sub-tab */}
            {inventorySubTab === "movements" && (
              <div className="ops-table-container">
                <table className="ops-table">
                  <thead>
                    <tr>
                      <th>Timestamp (UTC)</th>
                      <th>Movement Type</th>
                      <th>Product SKU</th>
                      <th>Warehouse</th>
                      <th>Quantity</th>
                      <th>Reference / PO</th>
                      <th>Operator</th>
                    </tr>
                  </thead>
                  <tbody>
                    {movements.map((m) => (
                      <tr key={m.id}>
                        <td>{new Date(m.created_at).toLocaleString()}</td>
                        <td>
                          <span
                            className={`status-badge ${
                              m.movement_type === "RECEIPT" ? "badge-receipt" : "badge-issue"
                            }`}
                          >
                            {m.movement_type}
                          </span>
                        </td>
                        <td>
                          <code>{m.product_sku || "—"}</code>
                        </td>
                        <td>
                          <b>{m.warehouse_code}</b>
                        </td>
                        <td>
                          <b>{m.quantity} units</b>
                        </td>
                        <td>{m.reference || "—"}</td>
                        <td>
                          <span style={{ color: "#475569" }}>{m.actor_name}</span>
                        </td>
                      </tr>
                    ))}
                    {movements.length === 0 && (
                      <tr>
                        <td colSpan={7} style={{ textAlign: "center", padding: 36, color: "#94a3b8" }}>
                          No stock movements recorded yet.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>

                <div className="pagination-bar">
                  <span>
                    Showing {movements.length} of {movementTotal} stock movements
                  </span>
                </div>
              </div>
            )}
          </div>
        )}

        {/* =========================================================================
            TAB 6: ORDERS & ORDER ITEMS
           ========================================================================= */}
        {activeTab === "orders" && (
          <div className="view-container">
            <div className="page-heading" style={{ paddingBottom: 16 }}>
              <div>
                <div className="eyebrow">
                  PHASE 4 · ORDER MANAGEMENT <span className="heading-dot" /> BACKEND PRICING INTEGRITY
                </div>
                <h1>
                  Customer & replenishment orders<span>.</span>
                </h1>
                <p>
                  Orders with multi-line items. Totals are strictly server-computed from the product catalog.
                </p>
              </div>
              <div>
                <button
                  className={canManageData ? "btn-primary" : "btn-secondary disabled-lock-btn"}
                  onClick={() => canManageData && setOrderModal(true)}
                  disabled={!canManageData}
                  title={canManageData ? "New Order" : "Requires Operations Manager or Admin role"}
                >
                  {canManageData ? <Plus size={15} /> : <Lock size={14} />} New Purchase Order
                </button>
              </div>
            </div>

            {/* Toolbar */}
            <div className="toolbar">
              <div className="toolbar-left">
                <input
                  type="text"
                  className="search-input"
                  placeholder="Search order number, customer…"
                  value={orderSearch}
                  onChange={(e) => setOrderSearch(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && void loadOrders()}
                />
                <select
                  className="filter-select"
                  value={orderStatusFilter}
                  onChange={(e) => setOrderStatusFilter(e.target.value)}
                >
                  <option value="">All Statuses</option>
                  <option value="PENDING">PENDING</option>
                  <option value="PROCESSING">PROCESSING</option>
                  <option value="SHIPPED">SHIPPED</option>
                  <option value="DELIVERED">DELIVERED</option>
                  <option value="CANCELLED">CANCELLED</option>
                </select>
                <button className="btn-secondary btn-sm" onClick={() => void loadOrders()}>
                  <Search size={13} /> Filter
                </button>
              </div>
              <div className="toolbar-right">
                <span className="badge-live-db">
                  <Database size={11} /> Live Order Engine
                </span>
              </div>
            </div>

            {/* Table */}
            <div className="ops-table-container">
              <table className="ops-table">
                <thead>
                  <tr>
                    <th>Order #</th>
                    <th>Customer Name</th>
                    <th>Date Created</th>
                    <th>Facility</th>
                    <th>Items</th>
                    <th>Total Amount</th>
                    <th>Priority</th>
                    <th>Status</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {ordersList.map((ord) => (
                    <tr key={ord.id}>
                      <td>
                        <b>{ord.order_number}</b>
                      </td>
                      <td>{ord.customer_name}</td>
                      <td>{new Date(ord.created_at).toLocaleDateString()}</td>
                      <td>{ord.warehouse_code || "Global"}</td>
                      <td>{ord.items.length} line(s)</td>
                      <td>
                        <b>${Number(ord.total_amount).toFixed(2)}</b>
                      </td>
                      <td>
                        <span
                          style={{
                            fontWeight: 700,
                            color:
                              ord.priority === "CRITICAL"
                                ? "#dc2626"
                                : ord.priority === "HIGH"
                                ? "#ea580c"
                                : "#475569",
                          }}
                        >
                          {ord.priority}
                        </span>
                      </td>
                      <td>
                        <span
                          className={`status-badge ${
                            ord.status === "PENDING"
                              ? "badge-pending"
                              : ord.status === "PROCESSING"
                              ? "badge-processing"
                              : ord.status === "SHIPPED"
                              ? "badge-shipped"
                              : ord.status === "DELIVERED"
                              ? "badge-delivered"
                              : "badge-cancelled"
                          }`}
                        >
                          {ord.status}
                        </span>
                      </td>
                      <td>
                        <button
                          className="btn-secondary btn-sm"
                          onClick={() => setSelectedOrder(ord)}
                        >
                          Details & Status &rarr;
                        </button>
                      </td>
                    </tr>
                  ))}
                  {ordersList.length === 0 && (
                    <tr>
                      <td colSpan={9} style={{ textAlign: "center", padding: 36, color: "#94a3b8" }}>
                        No orders found. Click "+ New Purchase Order" to register a customer order.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>

              <div className="pagination-bar">
                <span>
                  Showing {ordersList.length} of {orderTotal} orders
                </span>
                <div className="pagination-controls">
                  <button
                    className="page-btn"
                    disabled={orderPage <= 1}
                    onClick={() => setOrderPage((p) => Math.max(1, p - 1))}
                  >
                    Previous
                  </button>
                  <span>Page {orderPage}</span>
                  <button
                    className="page-btn"
                    disabled={ordersList.length < 15}
                    onClick={() => setOrderPage((p) => p + 1)}
                  >
                    Next
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* =========================================================================
            TAB 7: RISKS INTELLIGENCE (REAL OPERATIONAL RISK RADAR)
           ========================================================================= */}
        {activeTab === "risks" && (
          <div className="view-container">
            <div className="page-heading">
              <div>
                <div className="eyebrow">
                  REAL RISK INTELLIGENCE <span className="heading-dot" /> LIVE DATABASE RECORDS
                </div>
                <h1>Risk intelligence.</h1>
                <p>
                  Explainable, deterministic operational risk scoring across stockouts, supplier SLAs, overdue orders, and regional imbalances.
                </p>
              </div>
              <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
                <span className="badge-live-db">
                  <Database size={12} /> Deterministic Rules Engine
                </span>
                <button
                  className="refresh-button"
                  onClick={() => void loadDashboard()}
                  disabled={dashboardBusy}
                >
                  <RefreshCw size={14} className={dashboardBusy ? "spin" : ""} /> Refresh
                </button>
              </div>
            </div>

            <div className="risk-card-grid">
              {risks.map((r) => (
                <div key={r.id} className={`risk-card-p5 ${r.severity.toLowerCase()}`}>
                  <div className="rec-card-header">
                    <div className="rec-card-title">
                      <span className={`severity ${r.severity.toLowerCase()}`}>{r.severity}</span>
                      <span className="rec-tag">{r.category.replace(/_/g, " ")}</span>
                      <span>{r.entity_name || r.supplier || r.id}</span>
                    </div>
                    <div className="risk-score">
                      <b>{r.score} / 100</b>
                      <small>Risk Index</small>
                    </div>
                  </div>

                  <p style={{ margin: "8px 0 4px", fontSize: 13, color: "#1e293b", lineHeight: 1.5 }}>
                    {r.explanation || r.message}
                  </p>

                  {r.rules_triggered && r.rules_triggered.length > 0 && (
                    <div>
                      <small style={{ fontSize: 10, fontWeight: 700, color: "#64748b" }}>
                        OPERATIONAL RULES TRIGGERED:
                      </small>
                      <div className="risk-rules-pills">
                        {r.rules_triggered.map((rule, idx) => (
                          <span key={idx} className="rule-pill">
                            {rule}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {r.suggested_action && (
                    <div className="rec-action-callout" style={{ marginTop: 8 }}>
                      <BrainCircuit size={16} />
                      <div>
                        <b>Suggested Action:</b> {r.suggested_action}
                      </div>
                    </div>
                  )}

                  <div className="rec-meta-row" style={{ marginTop: 10 }}>
                    <span>Entity Type: <b>{r.entity_type || "system"}</b></span>
                    <span>Methodology: <b>{r.source === "statistical_baseline" ? "Statistical Baseline" : "Deterministic Rule Engine"}</b></span>
                    <span>Calculated At: <b>{r.calculated_at ? new Date(r.calculated_at).toLocaleTimeString() : "Live"}</b></span>
                  </div>
                </div>
              ))}

              {risks.length === 0 && (
                <div className="panel" style={{ textAlign: "center", padding: "48px 20px" }}>
                  <CheckCircle2 size={36} style={{ color: "#22c55e", margin: "0 auto 12px" }} />
                  <h3 style={{ margin: "0 0 6px", fontSize: 16, color: "#0f172a" }}>
                    No Operational Risks Detected
                  </h3>
                  <p style={{ margin: 0, fontSize: 12, color: "#64748b" }}>
                    All inventory levels satisfy safety stock thresholds, supplier reliability ratings are compliant with corporate SLAs, and orders are on schedule.
                  </p>
                </div>
              )}
            </div>
          </div>
        )}

        {/* =========================================================================
            TAB 8: DECISION APPROVALS & SAFE EXECUTION
           ========================================================================= */}
        {activeTab === "approvals" && (
          <div className="view-container">
            <div className="page-heading">
              <div>
                <div className="eyebrow">
                  HUMAN-IN-THE-LOOP <span className="heading-dot" /> AUDITABLE OPERATIONAL EXECUTION
                </div>
                <h1>Decision approvals.</h1>
                <p>
                  System-generated replenishment proposals requiring human review, transaction-safe execution, and complete audit logging.
                </p>
              </div>
              <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
                <span className="badge-live-db">
                  <Database size={12} /> Idempotent Transactions
                </span>
                <button
                  className="refresh-button"
                  onClick={() => void loadDashboard()}
                  disabled={dashboardBusy}
                >
                  <RefreshCw size={14} className={dashboardBusy ? "spin" : ""} /> Refresh
                </button>
              </div>
            </div>

            {/* Status Filter Sub-tabs */}
            <div className="subtab-bar">
              {["ALL", "PENDING", "APPROVED", "EXECUTED", "REJECTED"].map((st) => (
                <button
                  key={st}
                  className={`subtab-btn ${recStatusFilter === st ? "active" : ""}`}
                  onClick={() => setRecStatusFilter(st)}
                >
                  {st} {st !== "ALL" ? `(${recs.filter((r) => r.status === st).length})` : `(${recs.length})`}
                </button>
              ))}
            </div>

            <div className="recommendations-container" style={{ marginTop: 12 }}>
              {recs
                .filter((r) => recStatusFilter === "ALL" || r.status === recStatusFilter)
                .map((rec, idx) => (
                  <div key={rec.id} className="rec-card-expanded">
                    <div className="rec-card-header">
                      <div className="rec-card-title">
                        <span className="rec-number">{idx + 1}</span>
                        <span>{rec.title}</span>
                        <span className="rec-tag">{rec.recommendation_type || "PROPOSAL"}</span>
                        <span
                          className={`status-badge ${
                            rec.status === "PENDING"
                              ? "badge-pending"
                              : rec.status === "APPROVED"
                              ? "badge-approved"
                              : rec.status === "EXECUTED"
                              ? "badge-executed"
                              : "badge-rejected"
                          }`}
                        >
                          {rec.status || "PENDING"}
                        </span>
                      </div>

                      {/* Action buttons based on status */}
                      <div className="rec-actions">
                        {rec.status === "PENDING" && (
                          <>
                            <button
                              className={canDecide ? "reject-button" : "reject-button disabled-lock-btn"}
                              disabled={!canDecide}
                              onClick={() => canDecide && void handleApproval(rec.id, false)}
                              title={!canDecide ? "Requires Operations Manager or Admin role" : "Reject proposal"}
                            >
                              {!canDecide && <Lock size={12} style={{ marginRight: 4 }} />}
                              Reject
                            </button>
                            <button
                              className={canDecide ? "approve-button" : "approve-button disabled-lock-btn"}
                              disabled={!canDecide}
                              onClick={() => canDecide && void handleApproval(rec.id, true)}
                              title={!canDecide ? "Requires Operations Manager or Admin role" : "Approve proposal for execution"}
                            >
                              {canDecide ? <CheckCircle2 size={13} /> : <Lock size={12} />} Approve
                            </button>
                          </>
                        )}

                        {rec.status === "APPROVED" && (
                          <button
                            className={canManageData ? "execute-button" : "execute-button disabled-lock-btn"}
                            disabled={!canManageData}
                            onClick={() => canManageData && void handleExecute(rec.id)}
                            title={!canManageData ? "Requires Data Manage role" : "Execute approved proposal atomically"}
                          >
                            {canManageData ? <Package size={13} /> : <Lock size={12} />} Execute Action
                          </button>
                        )}

                        {rec.status === "EXECUTED" && (
                          <span className="status-badge badge-executed">
                            <CheckCircle2 size={12} /> Executed Safely
                          </span>
                        )}

                        {rec.status === "REJECTED" && (
                          <span className="status-badge badge-rejected">
                            <X size={12} /> Rejected by Operator
                          </span>
                        )}
                      </div>
                    </div>

                    <p style={{ margin: "4px 0 8px", fontSize: 13, color: "#334155" }}>
                      {rec.explanation || rec.reason}
                    </p>

                    {/* Proposed Action & Parameters */}
                    {rec.proposed_action && (
                      <div className="rec-action-callout">
                        <Package size={16} />
                        <div>
                          <b>Proposed Action:</b> <code>{rec.proposed_action}</code>
                          {rec.parameters && (
                            <span style={{ marginLeft: 10, fontSize: 11 }}>
                              Parameters: {JSON.stringify(rec.parameters)}
                            </span>
                          )}
                        </div>
                      </div>
                    )}

                    {/* Decision & Execution Audit Trail */}
                    {(rec.decided_by_name || rec.executed_at) && (
                      <div className="rec-meta-row" style={{ background: "#f8fafc", padding: "8px 12px", borderRadius: 6 }}>
                        {rec.decided_by_name && (
                          <span>
                            Decision Maker: <b>{rec.decided_by_name}</b> ({rec.decided_at ? new Date(rec.decided_at).toLocaleString() : ""})
                            {rec.decision_comment && <em> — "{rec.decision_comment}"</em>}
                          </span>
                        )}
                        {rec.executed_at && (
                          <span>
                            Executed: <b>{new Date(rec.executed_at).toLocaleString()}</b>
                            {rec.execution_result && (
                              <span style={{ marginLeft: 8 }}>
                                Result: <code>{JSON.stringify(rec.execution_result)}</code>
                              </span>
                            )}
                          </span>
                        )}
                      </div>
                    )}

                    <div className="rec-meta-row">
                      <span>Affected Entity: <b>{rec.entity_name || rec.entity_id || "System"}</b></span>
                      <span>Entity Type: <b>{rec.entity_type || "product"}</b></span>
                      <span>Created: <b>{rec.created_at ? new Date(rec.created_at).toLocaleString() : "Live"}</b></span>
                    </div>
                  </div>
                ))}

              {recs.length === 0 && (
                <div className="panel" style={{ textAlign: "center", padding: "48px 20px" }}>
                  <CheckCircle2 size={36} style={{ color: "#22c55e", margin: "0 auto 12px" }} />
                  <h3 style={{ margin: "0 0 6px", fontSize: 16, color: "#0f172a" }}>
                    No Pending Approvals
                  </h3>
                  <p style={{ margin: 0, fontSize: 12, color: "#64748b" }}>
                    All operational recommendations have been evaluated or executed.
                  </p>
                </div>
              )}
            </div>
          </div>
        )}

        {/* =========================================================================
            TAB 9: OPERATIONAL AI RADAR & ML EVALUATION
           ========================================================================= */}
        {activeTab === "analytics" && (
          <div className="view-container">
            <div className="page-heading">
              <div>
                <div className="eyebrow">
                  OPERATIONAL ANALYTICS & TRANSPARENT ML RADAR <span className="heading-dot" /> PHASE 5
                </div>
                <h1>Operational AI Radar.</h1>
                <p>
                  Genuine operational metrics derived from database tables, evaluated with chronological temporal split without synthetic data fabrication.
                </p>
              </div>
              <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
                <span className="badge-live-db">
                  <Database size={12} /> Anti-Data-Leakage Model
                </span>
                <button
                  className="refresh-button"
                  onClick={() => void loadDashboard()}
                  disabled={dashboardBusy}
                >
                  <RefreshCw size={14} className={dashboardBusy ? "spin" : ""} /> Refresh
                </button>
              </div>
            </div>

            {/* Operational Summary Grid */}
            <div className="analytics-stat-grid">
              <div className="stat-box">
                <div className="stat-box-title">Active Product Catalog</div>
                <div className="stat-box-value">
                  {analyticsSummary?.active_products ?? "0"} <span style={{ fontSize: 14, color: "#64748b" }}>/ {analyticsSummary?.total_products ?? "0"}</span>
                </div>
                <div className="stat-box-subtitle">Total SKUs in inventory master</div>
              </div>

              <div className="stat-box">
                <div className="stat-box-title">Total Inventory Units</div>
                <div className="stat-box-value">
                  {analyticsSummary?.total_inventory_units ?? "0"}
                </div>
                <div className="stat-box-subtitle">
                  Available: {analyticsSummary?.available_inventory_units ?? "0"} · Reserved: {analyticsSummary?.reserved_inventory_units ?? "0"}
                </div>
              </div>

              <div className="stat-box">
                <div className="stat-box-title">Inventory Valuation</div>
                <div className="stat-box-value" style={{ color: "#2563eb" }}>
                  ${analyticsSummary?.total_inventory_valuation ?? "0.00"}
                </div>
                <div className="stat-box-subtitle">Cost-weighted warehouse assets</div>
              </div>

              <div className="stat-box">
                <div className="stat-box-title">Stockout Vulnerabilities</div>
                <div className="stat-box-value" style={{ color: (analyticsSummary?.stockout_items_count ?? 0) > 0 ? "#ef4444" : "#10b981" }}>
                  {analyticsSummary?.stockout_items_count ?? "0"}
                </div>
                <div className="stat-box-subtitle">
                  Low stock: {analyticsSummary?.low_stock_items_count ?? "0"} SKUs
                </div>
              </div>
            </div>

            {/* Machine Learning Model Evaluation Radar Card */}
            <div className="ml-radar-card">
              <div className="rec-card-header">
                <div>
                  <h2 style={{ margin: "0 0 4px", fontSize: 16, color: "#0f172a" }}>
                    {mlEvaluation?.model_name || "Operational Delay Risk Estimator"}
                  </h2>
                  <p style={{ margin: 0, fontSize: 12, color: "#64748b" }}>
                    Task: {mlEvaluation?.task_type || "Binary Classification"} · Methodology: <b>70/30 Chronological Train/Test Split</b> (Anti-Data-Leakage)
                  </p>
                </div>
                <span
                  className={`status-badge ${
                    mlEvaluation?.status === "evaluated" ? "badge-delivered" : "badge-pending"
                  }`}
                >
                  {mlEvaluation?.status === "evaluated" ? "Model Evaluated" : "Data Sufficiency Gated"}
                </span>
              </div>

              {mlEvaluation?.status === "evaluated" && (
                <div>
                  <div className="ml-metrics-row">
                    <div className="metric-pill-box">
                      <small>Sample Orders</small>
                      <b>{mlEvaluation.samples_count}</b>
                    </div>
                    <div className="metric-pill-box">
                      <small>Accuracy</small>
                      <b style={{ color: "#2563eb" }}>
                        {mlEvaluation.accuracy !== null ? `${(mlEvaluation.accuracy * 100).toFixed(1)}%` : "—"}
                      </b>
                    </div>
                    <div className="metric-pill-box">
                      <small>Precision</small>
                      <b>{mlEvaluation.precision !== null ? mlEvaluation.precision : "—"}</b>
                    </div>
                    <div className="metric-pill-box">
                      <small>Recall</small>
                      <b>{mlEvaluation.recall !== null ? mlEvaluation.recall : "—"}</b>
                    </div>
                    <div className="metric-pill-box">
                      <small>F1 Score</small>
                      <b style={{ color: "#059669" }}>
                        {mlEvaluation.f1_score !== null ? mlEvaluation.f1_score : "—"}
                      </b>
                    </div>
                  </div>

                  {mlEvaluation.baseline_comparison && (
                    <div style={{ background: "#f8fafc", padding: "12px 16px", borderRadius: 8, fontSize: 12, color: "#334155" }}>
                      <b>Baseline Comparison:</b> Majority Class Accuracy is{" "}
                      <b>{((mlEvaluation.baseline_comparison.majority_class_accuracy || 0) * 100).toFixed(1)}%</b>.
                      Model Improvement Delta:{" "}
                      <b>{((mlEvaluation.baseline_comparison.model_improvement_delta || 0) * 100).toFixed(1)}%</b>.
                    </div>
                  )}

                  <p style={{ fontSize: 12, color: "#64748b", marginTop: 10 }}>
                    {mlEvaluation.evaluation_notes}
                  </p>
                </div>
              )}

              {mlEvaluation?.status === "insufficient_data" && (
                <div className="data-req-list">
                  <div style={{ display: "flex", alignItems: "center", gap: 8, fontWeight: 700 }}>
                    <AlertTriangle size={16} /> Transparent Model Gating Notice
                  </div>
                  <p style={{ margin: "6px 0", fontSize: 12 }}>
                    {mlEvaluation.evaluation_notes}
                  </p>
                  <b>Required Operational Data Before ML Production Training:</b>
                  <ul>
                    {mlEvaluation.data_requirements?.map((req, idx) => (
                      <li key={idx}>{req}</li>
                    ))}
                  </ul>
                </div>
              )}

              {!canViewAnalytics && (
                <div style={{ marginTop: 14, color: "#92400e", fontSize: 12 }}>
                  <Lock size={12} style={{ display: "inline", marginRight: 5 }} />
                  Full ML evaluation metrics restricted to Analyst and Operations Manager roles.
                </div>
              )}
            </div>
          </div>
        )}

      </main>

      {/* =========================================================================
          MODALS
         ========================================================================= */}

      {/* 1. Create Supplier Modal */}
      {supplierModal && (
        <div className="modal-backdrop">
          <div className="modal-card">
            <div className="modal-header">
              <h3>Create New Supplier</h3>
              <button className="close-btn" onClick={() => setSupplierModal(false)}>
                &times;
              </button>
            </div>
            <form onSubmit={handleCreateSupplier}>
              <div className="modal-body">
                <div className="form-grid">
                  <div className="form-group">
                    <label>Supplier Code *</label>
                    <input
                      required
                      placeholder="e.g. SUP-MICRO-01"
                      value={supplierForm.code}
                      onChange={(e) => setSupplierForm({ ...supplierForm, code: e.target.value.toUpperCase() })}
                    />
                  </div>
                  <div className="form-group">
                    <label>Supplier Name *</label>
                    <input
                      required
                      placeholder="e.g. MicroTech Global"
                      value={supplierForm.name}
                      onChange={(e) => setSupplierForm({ ...supplierForm, name: e.target.value })}
                    />
                  </div>
                </div>
                <div className="form-grid">
                  <div className="form-group">
                    <label>Contact Email</label>
                    <input
                      type="email"
                      placeholder="sales@vendor.com"
                      value={supplierForm.contact_email}
                      onChange={(e) => setSupplierForm({ ...supplierForm, contact_email: e.target.value })}
                    />
                  </div>
                  <div className="form-group">
                    <label>Contact Phone</label>
                    <input
                      placeholder="+1-555-0100"
                      value={supplierForm.contact_phone}
                      onChange={(e) => setSupplierForm({ ...supplierForm, contact_phone: e.target.value })}
                    />
                  </div>
                </div>
                <div className="form-grid">
                  <div className="form-group">
                    <label>Lead Time (Days)</label>
                    <input
                      type="number"
                      min={0}
                      value={supplierForm.lead_time_days}
                      onChange={(e) =>
                        setSupplierForm({ ...supplierForm, lead_time_days: Number(e.target.value) })
                      }
                    />
                  </div>
                  <div className="form-group">
                    <label>Reliability Score (0.00 - 1.00)</label>
                    <input
                      type="number"
                      step="0.01"
                      min="0.00"
                      max="1.00"
                      value={supplierForm.reliability_score}
                      onChange={(e) =>
                        setSupplierForm({ ...supplierForm, reliability_score: e.target.value })
                      }
                    />
                  </div>
                </div>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn-secondary" onClick={() => setSupplierModal(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn-primary">
                  Save Supplier
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* 2. Create Product Modal */}
      {productModal && (
        <div className="modal-backdrop">
          <div className="modal-card">
            <div className="modal-header">
              <h3>Add Product to Catalog</h3>
              <button className="close-btn" onClick={() => setProductModal(false)}>
                &times;
              </button>
            </div>
            <form onSubmit={handleCreateProduct}>
              <div className="modal-body">
                <div className="form-grid">
                  <div className="form-group">
                    <label>Product SKU *</label>
                    <input
                      required
                      placeholder="e.g. SKU-SEN-001"
                      value={productForm.sku}
                      onChange={(e) => setProductForm({ ...productForm, sku: e.target.value.toUpperCase() })}
                    />
                  </div>
                  <div className="form-group">
                    <label>Product Name *</label>
                    <input
                      required
                      placeholder="e.g. Optical Sensor"
                      value={productForm.name}
                      onChange={(e) => setProductForm({ ...productForm, name: e.target.value })}
                    />
                  </div>
                </div>
                <div className="form-grid">
                  <div className="form-group">
                    <label>Category *</label>
                    <input
                      required
                      placeholder="e.g. Sensors, Hardware"
                      value={productForm.category}
                      onChange={(e) => setProductForm({ ...productForm, category: e.target.value })}
                    />
                  </div>
                  <div className="form-group">
                    <label>Assigned Supplier</label>
                    <select
                      value={productForm.supplier_id}
                      onChange={(e) => setProductForm({ ...productForm, supplier_id: e.target.value })}
                    >
                      <option value="">No Supplier Attached</option>
                      {suppliers.map((s) => (
                        <option key={s.id} value={s.id}>
                          {s.name} ({s.code})
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
                <div className="form-grid">
                  <div className="form-group">
                    <label>Unit Price ($) *</label>
                    <input
                      type="number"
                      step="0.01"
                      min="0.00"
                      required
                      value={productForm.unit_price}
                      onChange={(e) => setProductForm({ ...productForm, unit_price: e.target.value })}
                    />
                  </div>
                  <div className="form-group">
                    <label>Unit Cost ($) *</label>
                    <input
                      type="number"
                      step="0.01"
                      min="0.00"
                      required
                      value={productForm.unit_cost}
                      onChange={(e) => setProductForm({ ...productForm, unit_cost: e.target.value })}
                    />
                  </div>
                </div>
                <div className="form-grid">
                  <div className="form-group">
                    <label>Reorder Point (Threshold)</label>
                    <input
                      type="number"
                      min={0}
                      value={productForm.reorder_point}
                      onChange={(e) =>
                        setProductForm({ ...productForm, reorder_point: Number(e.target.value) })
                      }
                    />
                  </div>
                  <div className="form-group">
                    <label>Safety Stock</label>
                    <input
                      type="number"
                      min={0}
                      value={productForm.safety_stock}
                      onChange={(e) =>
                        setProductForm({ ...productForm, safety_stock: Number(e.target.value) })
                      }
                    />
                  </div>
                </div>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn-secondary" onClick={() => setProductModal(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn-primary">
                  Save Product
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* 3. Create Warehouse Modal */}
      {warehouseModal && (
        <div className="modal-backdrop">
          <div className="modal-card">
            <div className="modal-header">
              <h3>Create Warehouse Facility</h3>
              <button className="close-btn" onClick={() => setWarehouseModal(false)}>
                &times;
              </button>
            </div>
            <form onSubmit={handleCreateWarehouse}>
              <div className="modal-body">
                <div className="form-grid">
                  <div className="form-group">
                    <label>Warehouse Code *</label>
                    <input
                      required
                      placeholder="e.g. WH-NORTH-01"
                      value={warehouseForm.code}
                      onChange={(e) => setWarehouseForm({ ...warehouseForm, code: e.target.value.toUpperCase() })}
                    />
                  </div>
                  <div className="form-group">
                    <label>Warehouse Name *</label>
                    <input
                      required
                      placeholder="e.g. Northern Hub"
                      value={warehouseForm.name}
                      onChange={(e) => setWarehouseForm({ ...warehouseForm, name: e.target.value })}
                    />
                  </div>
                </div>
                <div className="form-grid">
                  <div className="form-group">
                    <label>Physical Location *</label>
                    <input
                      required
                      placeholder="e.g. Chicago, IL"
                      value={warehouseForm.location}
                      onChange={(e) => setWarehouseForm({ ...warehouseForm, location: e.target.value })}
                    />
                  </div>
                  <div className="form-group">
                    <label>Max Storage Capacity *</label>
                    <input
                      type="number"
                      min={1}
                      required
                      value={warehouseForm.capacity}
                      onChange={(e) => setWarehouseForm({ ...warehouseForm, capacity: Number(e.target.value) })}
                    />
                  </div>
                </div>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn-secondary" onClick={() => setWarehouseModal(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn-primary">
                  Save Facility
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* 4. Receive Stock Modal */}
      {receiptModal && (
        <div className="modal-backdrop">
          <div className="modal-card">
            <div className="modal-header">
              <h3>Receive Inbound Stock (PO)</h3>
              <button className="close-btn" onClick={() => setReceiptModal(false)}>
                &times;
              </button>
            </div>
            <form onSubmit={handleReceiveStock}>
              <div className="modal-body">
                <div className="form-group">
                  <label>Catalog Product *</label>
                  <select
                    required
                    value={receiptForm.product_id}
                    onChange={(e) => setReceiptForm({ ...receiptForm, product_id: e.target.value })}
                  >
                    <option value="">Select Catalog Product…</option>
                    {products.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.sku} — {p.name}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="form-group">
                  <label>Receiving Warehouse *</label>
                  <select
                    required
                    value={receiptForm.warehouse_id}
                    onChange={(e) => setReceiptForm({ ...receiptForm, warehouse_id: e.target.value })}
                  >
                    <option value="">Select Destination Warehouse…</option>
                    {warehouses.map((w) => (
                      <option key={w.id} value={w.id}>
                        {w.code} — {w.name} ({w.location})
                      </option>
                    ))}
                  </select>
                </div>
                <div className="form-grid">
                  <div className="form-group">
                    <label>Quantity to Receive *</label>
                    <input
                      type="number"
                      min={1}
                      required
                      value={receiptForm.quantity}
                      onChange={(e) => setReceiptForm({ ...receiptForm, quantity: Number(e.target.value) })}
                    />
                  </div>
                  <div className="form-group">
                    <label>PO Reference / Tracking</label>
                    <input
                      placeholder="e.g. PO-2026-8812"
                      value={receiptForm.reference}
                      onChange={(e) => setReceiptForm({ ...receiptForm, reference: e.target.value })}
                    />
                  </div>
                </div>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn-secondary" onClick={() => setReceiptModal(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn-primary">
                  Process Receipt & Record Movement
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* 5. Issue Stock Modal */}
      {issueModal && (
        <div className="modal-backdrop">
          <div className="modal-card">
            <div className="modal-header">
              <h3>Issue Outbound Stock (Dispatch)</h3>
              <button className="close-btn" onClick={() => setIssueModal(false)}>
                &times;
              </button>
            </div>
            <form onSubmit={handleIssueStock}>
              <div className="modal-body">
                <div className="form-group">
                  <label>Catalog Product *</label>
                  <select
                    required
                    value={issueForm.product_id}
                    onChange={(e) => setIssueForm({ ...issueForm, product_id: e.target.value })}
                  >
                    <option value="">Select Catalog Product…</option>
                    {products.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.sku} — {p.name}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="form-group">
                  <label>Source Warehouse *</label>
                  <select
                    required
                    value={issueForm.warehouse_id}
                    onChange={(e) => setIssueForm({ ...issueForm, warehouse_id: e.target.value })}
                  >
                    <option value="">Select Source Warehouse…</option>
                    {warehouses.map((w) => (
                      <option key={w.id} value={w.id}>
                        {w.code} — {w.name} ({w.location})
                      </option>
                    ))}
                  </select>
                </div>
                <div className="form-grid">
                  <div className="form-group">
                    <label>Quantity to Issue *</label>
                    <input
                      type="number"
                      min={1}
                      required
                      value={issueForm.quantity}
                      onChange={(e) => setIssueForm({ ...issueForm, quantity: Number(e.target.value) })}
                    />
                  </div>
                  <div className="form-group">
                    <label>Dispatch Note / Manifest</label>
                    <input
                      placeholder="e.g. OUT-ORDER-9921"
                      value={issueForm.reference}
                      onChange={(e) => setIssueForm({ ...issueForm, reference: e.target.value })}
                    />
                  </div>
                </div>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn-secondary" onClick={() => setIssueModal(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn-primary">
                  Process Issue & Record Movement
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* 6. Create Order Modal */}
      {orderModal && (
        <div className="modal-backdrop">
          <div className="modal-card" style={{ maxWidth: 640 }}>
            <div className="modal-header">
              <h3>Create New Purchase Order</h3>
              <button className="close-btn" onClick={() => setOrderModal(false)}>
                &times;
              </button>
            </div>
            <form onSubmit={handleCreateOrder}>
              <div className="modal-body">
                <div className="form-grid">
                  <div className="form-group">
                    <label>Customer Name *</label>
                    <input
                      required
                      placeholder="e.g. Apex Aerospace Inc."
                      value={orderForm.customer_name}
                      onChange={(e) => setOrderForm({ ...orderForm, customer_name: e.target.value })}
                    />
                  </div>
                  <div className="form-group">
                    <label>Priority</label>
                    <select
                      value={orderForm.priority}
                      onChange={(e) => setOrderForm({ ...orderForm, priority: e.target.value })}
                    >
                      <option value="LOW">LOW</option>
                      <option value="NORMAL">NORMAL</option>
                      <option value="HIGH">HIGH</option>
                      <option value="CRITICAL">CRITICAL</option>
                    </select>
                  </div>
                </div>
                <div className="form-group">
                  <label>Fulfillment Warehouse (Optional)</label>
                  <select
                    value={orderForm.warehouse_id}
                    onChange={(e) => setOrderForm({ ...orderForm, warehouse_id: e.target.value })}
                  >
                    <option value="">Auto-Assign / Default Facility</option>
                    {warehouses.map((w) => (
                      <option key={w.id} value={w.id}>
                        {w.code} — {w.name} ({w.location})
                      </option>
                    ))}
                  </select>
                </div>

                <div style={{ marginTop: 8 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <label style={{ fontSize: 11, fontWeight: 700, color: "#334155" }}>
                      ORDER LINE ITEMS (PRICED FROM CATALOG)
                    </label>
                    <button
                      type="button"
                      className="btn-secondary btn-sm"
                      onClick={() =>
                        setOrderForm({
                          ...orderForm,
                          items: [...orderForm.items, { product_id: "", quantity: 1 }],
                        })
                      }
                    >
                      + Add Item
                    </button>
                  </div>

                  <div style={{ marginTop: 8, display: "flex", flexDirection: "column", gap: 8 }}>
                    {orderForm.items.map((item, idx) => {
                      const selectedProd = products.find((p) => p.id === item.product_id);
                      const unitPrice = selectedProd ? Number(selectedProd.unit_price) : 0;
                      const lineSubtotal = unitPrice * item.quantity;
                      return (
                        <div
                          key={idx}
                          style={{
                            display: "flex",
                            alignItems: "center",
                            gap: 8,
                            background: "#f8fafc",
                            padding: 8,
                            borderRadius: 8,
                          }}
                        >
                          <select
                            style={{ flex: 1, padding: 8, borderRadius: 6, border: "1px solid #cbd5e1" }}
                            value={item.product_id}
                            required
                            onChange={(e) => {
                              const newItems = [...orderForm.items];
                              newItems[idx].product_id = e.target.value;
                              setOrderForm({ ...orderForm, items: newItems });
                            }}
                          >
                            <option value="">Select Product…</option>
                            {products.map((p) => (
                              <option key={p.id} value={p.id}>
                                {p.sku} — {p.name} (${Number(p.unit_price).toFixed(2)})
                              </option>
                            ))}
                          </select>
                          <input
                            type="number"
                            min={1}
                            style={{ width: 80, padding: 8, borderRadius: 6, border: "1px solid #cbd5e1" }}
                            value={item.quantity}
                            onChange={(e) => {
                              const newItems = [...orderForm.items];
                              newItems[idx].quantity = Number(e.target.value);
                              setOrderForm({ ...orderForm, items: newItems });
                            }}
                          />
                          <span style={{ fontSize: 11, minWidth: 70, textAlign: "right", fontWeight: 700 }}>
                            ${lineSubtotal.toFixed(2)}
                          </span>
                          {orderForm.items.length > 1 && (
                            <button
                              type="button"
                              style={{ background: "none", border: "none", color: "#94a3b8", cursor: "pointer" }}
                              onClick={() => {
                                setOrderForm({
                                  ...orderForm,
                                  items: orderForm.items.filter((_, i) => i !== idx),
                                });
                              }}
                            >
                              <X size={15} />
                            </button>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn-secondary" onClick={() => setOrderModal(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn-primary">
                  Create Order & Calculate Totals
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* 7. Order Details & Status Transition Modal */}
      {selectedOrder && (
        <div className="modal-backdrop">
          <div className="modal-card" style={{ maxWidth: 640 }}>
            <div className="modal-header">
              <div>
                <h3>Order {selectedOrder.order_number}</h3>
                <small style={{ color: "#64748b" }}>
                  Customer: <b>{selectedOrder.customer_name}</b> · Created:{" "}
                  {new Date(selectedOrder.created_at).toLocaleString()}
                </small>
              </div>
              <button className="close-btn" onClick={() => setSelectedOrder(null)}>
                &times;
              </button>
            </div>
            <div className="modal-body">
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  background: "#f8fafc",
                  padding: 12,
                  borderRadius: 8,
                }}
              >
                <div>
                  <small style={{ display: "block", color: "#64748b" }}>Current Status</small>
                  <span
                    className={`status-badge ${
                      selectedOrder.status === "PENDING"
                        ? "badge-pending"
                        : selectedOrder.status === "PROCESSING"
                        ? "badge-processing"
                        : selectedOrder.status === "SHIPPED"
                        ? "badge-shipped"
                        : selectedOrder.status === "DELIVERED"
                        ? "badge-delivered"
                        : "badge-cancelled"
                    }`}
                  >
                    {selectedOrder.status}
                  </span>
                </div>
                <div>
                  <small style={{ display: "block", color: "#64748b" }}>Order Priority</small>
                  <b>{selectedOrder.priority}</b>
                </div>
                <div>
                  <small style={{ display: "block", color: "#64748b" }}>Backend Verified Total</small>
                  <b style={{ fontSize: 16, color: "#1e293b" }}>${Number(selectedOrder.total_amount).toFixed(2)}</b>
                </div>
              </div>

              {/* Status Machine Progression */}
              <div style={{ marginTop: 8 }}>
                <small style={{ display: "block", fontWeight: 700, color: "#475569", marginBottom: 6 }}>
                  STATE MACHINE PROGRESSION (RBAC ENFORCED)
                </small>
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                  {selectedOrder.status === "PENDING" && (
                    <>
                      <button
                        className={canManageData ? "btn-primary btn-sm" : "btn-primary btn-sm disabled-lock-btn"}
                        disabled={!canManageData}
                        onClick={() => canManageData && void handleUpdateOrderStatus(selectedOrder.id, "PROCESSING")}
                      >
                        Advance to PROCESSING &rarr;
                      </button>
                      <button
                        className={canManageData ? "btn-danger btn-sm" : "btn-danger btn-sm disabled-lock-btn"}
                        disabled={!canManageData}
                        onClick={() => canManageData && void handleUpdateOrderStatus(selectedOrder.id, "CANCELLED")}
                      >
                        Cancel Order
                      </button>
                    </>
                  )}
                  {selectedOrder.status === "PROCESSING" && (
                    <>
                      <button
                        className={canManageData ? "btn-primary btn-sm" : "btn-primary btn-sm disabled-lock-btn"}
                        disabled={!canManageData}
                        onClick={() => canManageData && void handleUpdateOrderStatus(selectedOrder.id, "SHIPPED")}
                      >
                        Dispatch / Mark as SHIPPED &rarr;
                      </button>
                      <button
                        className={canManageData ? "btn-danger btn-sm" : "btn-danger btn-sm disabled-lock-btn"}
                        disabled={!canManageData}
                        onClick={() => canManageData && void handleUpdateOrderStatus(selectedOrder.id, "CANCELLED")}
                      >
                        Cancel Order
                      </button>
                    </>
                  )}
                  {selectedOrder.status === "SHIPPED" && (
                    <>
                      <button
                        className={canManageData ? "btn-primary btn-sm" : "btn-primary btn-sm disabled-lock-btn"}
                        disabled={!canManageData}
                        onClick={() => canManageData && void handleUpdateOrderStatus(selectedOrder.id, "DELIVERED")}
                      >
                        Confirm Delivery (DELIVERED) &check;
                      </button>
                      <button
                        className={canManageData ? "btn-danger btn-sm" : "btn-danger btn-sm disabled-lock-btn"}
                        disabled={!canManageData}
                        onClick={() => canManageData && void handleUpdateOrderStatus(selectedOrder.id, "CANCELLED")}
                      >
                        Cancel Order
                      </button>
                    </>
                  )}
                  {(selectedOrder.status === "DELIVERED" || selectedOrder.status === "CANCELLED") && (
                    <span style={{ fontSize: 11, color: "#64748b" }}>
                      This order is in terminal state ({selectedOrder.status}). No further transitions allowed.
                    </span>
                  )}
                </div>
              </div>

              {/* Line Items Table */}
              <div style={{ marginTop: 12 }}>
                <small style={{ display: "block", fontWeight: 700, color: "#475569", marginBottom: 6 }}>
                  ORDER LINE ITEMS
                </small>
                <table className="ops-table" style={{ fontSize: 11 }}>
                  <thead>
                    <tr>
                      <th>Product SKU</th>
                      <th>Product Name</th>
                      <th>Quantity</th>
                      <th>Catalog Unit Price</th>
                      <th>Line Subtotal</th>
                    </tr>
                  </thead>
                  <tbody>
                    {selectedOrder.items.map((it) => (
                      <tr key={it.id}>
                        <td>
                          <code>{it.product_sku || "—"}</code>
                        </td>
                        <td>{it.product_name || "—"}</td>
                        <td>
                          <b>{it.quantity}</b>
                        </td>
                        <td>${Number(it.unit_price).toFixed(2)}</td>
                        <td>
                          <b>${Number(it.subtotal).toFixed(2)}</b>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn-secondary" onClick={() => setSelectedOrder(null)}>
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
