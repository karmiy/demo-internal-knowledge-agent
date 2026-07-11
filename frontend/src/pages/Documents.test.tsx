import { render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { api } from "../api/client";
import { Documents } from "./Documents";

afterEach(() => vi.restoreAllMocks());

it("shows ingestion status returned by the admin API", async () => {
  vi.spyOn(api, "documents").mockResolvedValue([
    { id: "12345678-abcd", title: "工程指南", status: "ready", error: null },
  ]);
  render(<Documents token="token" />);
  expect(await screen.findByText("工程指南")).toBeVisible();
  expect(screen.getByText("ready")).toBeVisible();
});
