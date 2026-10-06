const { z } = require('zod');
const authService = require('../services/authService');
const asyncHandler = require('../utils/asyncHandler');

const registerSchema = z.object({
  name: z.string().trim().min(2).max(80),
  email: z.string().trim().email(),
  password: z
    .string()
    .min(8, 'must be at least 8 characters')
    .regex(/[A-Za-z]/, 'must contain a letter')
    .regex(/\d/, 'must contain a number'),
});

const loginSchema = z.object({
  email: z.string().trim().email(),
  password: z.string().min(1),
});

const register = asyncHandler(async (req, res) => {
  const data = await authService.register(req.body);
  res.status(201).json({ success: true, data });
});

const login = asyncHandler(async (req, res) => {
  const data = await authService.login(req.body);
  res.json({ success: true, data });
});

const me = asyncHandler(async (req, res) => {
  res.json({ success: true, data: { user: authService.toPublic(req.user) } });
});

module.exports = { register, login, me, registerSchema, loginSchema };