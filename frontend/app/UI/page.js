import { redirect } from "next/navigation";

export default function UIPage() {
  redirect(
    `${process.env.FLASK_API_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:5000"}/UI`,
  );
}
