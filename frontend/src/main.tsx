import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter } from "react-router-dom";
import "maplibre-gl/dist/maplibre-gl.css";

import { App } from "./App";
import "./styles.css";

const queryClient = new QueryClient();
const root = document.getElementById("root");

if (!root) {
  throw new Error("Root element not found.");
}

ReactDOM.createRoot(root).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter
        future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
      >
        <App />
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>,
);
