import "./globals.css";
import type { Metadata } from "next";
export const metadata: Metadata = { title: "AEGIS — Protocol Intelligence", description: "Read-only DeFi protocol intelligence and smart-contract security research workbench." };
export default function RootLayout({children}:{children:React.ReactNode}) { return <html lang="en"><body>{children}</body></html>; }
