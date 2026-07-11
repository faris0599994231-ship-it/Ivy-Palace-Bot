import { Router, type IRouter } from "express";

const router: IRouter = Router();

// Lightweight endpoints for external uptime services to keep the
// container awake. No auth, no dependencies — just a fast 200 OK.
router.get("/", (_req, res) => {
  res.status(200).send("OK");
});

router.get("/ping", (_req, res) => {
  res.status(200).send("pong");
});

export default router;
