import React from "react";
import { createRoot } from "react-dom/client";
import { InvoiceReviewPage } from "./features/invoice-review/InvoiceReviewPage";
import "./styles.css";
import "./upload-help.css";

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <InvoiceReviewPage />
  </React.StrictMode>,
);
