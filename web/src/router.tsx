import { createBrowserRouter } from "react-router-dom";
import DashboardPage from "./pages/DashboardPage";
import TransferPage from "./pages/TransferPage";
import DemoScenariosPage from "./pages/DemoScenariosPage";

export const routes = [
  { path: "/", element: <DashboardPage /> },
  { path: "/transfer", element: <TransferPage /> },
  { path: "/demo", element: <DemoScenariosPage /> },
];

export const router = createBrowserRouter(routes);
