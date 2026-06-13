import { motion } from "framer-motion";
import { Link } from "react-router-dom";

/**
 * The outro deliberately breaks the dark language: calm, near-white, still. No
 * stars, no globe. Just reality, and a slow fade.
 */
export default function Outro() {
  return (
    <motion.main
      animate={{ opacity: 1 }}
      className="flex min-h-screen flex-col items-center justify-center gap-3 bg-thanks px-6 text-thanks-text"
      initial={{ opacity: 0 }}
      transition={{ duration: 1.6, ease: "easeOut" }}
    >
      <p className="text-3xl font-light sm:text-4xl">thank you.</p>
      <p className="text-3xl font-light sm:text-4xl">and thank you, Fred.</p>
      <Link
        className="mt-10 text-xs lowercase tracking-wider text-thanks-text underline-offset-4 opacity-50 transition-opacity hover:opacity-100"
        to="/"
      >
        restart
      </Link>
    </motion.main>
  );
}
