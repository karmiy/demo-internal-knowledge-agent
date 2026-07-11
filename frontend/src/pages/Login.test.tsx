import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";
import { Login } from "./Login";

it("submits demo credentials", async () => {
  const login = vi.fn().mockResolvedValue(undefined);
  render(<Login onLogin={login} />);
  await userEvent.click(screen.getByRole("button", { name: "进入知识库 →" }));
  expect(login).toHaveBeenCalledWith("alice.programmer", "demo-password");
});
