import { NextResponse } from "next/server";

export async function GET() {
  return NextResponse.json({ error: "XSUAA authentication not configured" }, { status: 501 });
}
