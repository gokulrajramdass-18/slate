import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

export function middleware(request: NextRequest) {
  // Only run on root path
  if (request.nextUrl.pathname === '/') {
    // Check if accessed through AppRouter (has JSESSIONID cookie)
    const hasSession = request.cookies.has('JSESSIONID');
    
    if (hasSession) {
      // Has XSUAA session, redirect to dashboard
      return NextResponse.redirect(new URL('/dashboard', request.url));
    }
  }
  
  return NextResponse.next();
}

export const config = {
  matcher: '/',
};
