import { Component, type ReactNode } from "react";

/** 8.5: one card failing (a field missing from an answer) used to blank the whole app; now only that card
 * steps aside, quietly. */
export class WidgetBoundary extends Component<{ children: ReactNode; name?: string }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  componentDidCatch(error: unknown) { console.warn(`A card (${this.props.name ?? "unnamed"}) failed and was left out:`, error); }
  render() { return this.state.failed ? null : this.props.children; }
}
