import { NextResponse } from "next/server";

export async function GET() {
  return NextResponse.json({
    apiUrl: process.env.NEXT_PUBLIC_API_URL || "http://localhost:5055/api",
    environment: process.env.NODE_ENV || "development",
  });
}
