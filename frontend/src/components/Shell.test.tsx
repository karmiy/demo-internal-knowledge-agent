import { render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { Shell } from "./Shell";

it("hides document administration from non-admin users", () => {
  render(<Shell user={{ id: "1", username: "alice", department: "engineering", roles: ["programmer"] }} page="chat" onNavigate={vi.fn()} onLogout={vi.fn()}><p>content</p></Shell>);
  expect(screen.queryByRole("button", { name: /文档管理/ })).not.toBeInTheDocument();
});
