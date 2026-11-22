// Content script entry (built as a single classic-script IIFE by scripts/build.mjs).
import css from "./styles.css?inline";
import { mountGuardian } from "./mountGuardian";

mountGuardian(css);