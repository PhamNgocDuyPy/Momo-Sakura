import { render, screen } from "@testing-library/react";
import { RouterProvider, createMemoryRouter } from "react-router-dom";
import { routes } from "../src/router";

describe("router", () => {
  it.each([
    ["/", "Tổng quan"],
    ["/transfer", "Chuyển tiền"],
    ["/demo", "Kịch bản demo"],
  ])("renders %s", (path, heading) => {
    const router = createMemoryRouter(routes, { initialEntries: [path] });
    render(<RouterProvider router={router} />);
    expect(screen.getByRole("heading", { name: heading })).toBeInTheDocument();
  });
});
