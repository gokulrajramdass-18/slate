import { NextResponse } from "next/server";

export async function POST() {
  return NextResponse.json({ error: "XSUAA authentication not configured" }, { status: 501 });
}
