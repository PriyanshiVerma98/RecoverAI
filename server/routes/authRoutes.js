const router = require('express').Router();
const rateLimit = require('express-rate-limit');
const ctrl = require('../controllers/authController');
const validate = require('../middleware/validate');
const { protect } = require('../middleware/auth');

const authLimiter =
  process.env.NODE_ENV === 'test'
    ? (req, res, next) => next()
    : rateLimit({
        windowMs: 15 * 60 * 1000,
        limit: 30,
        message: { success: false, message: 'Too many attempts, try again later' },
      });

router.post('/register', authLimiter, validate(ctrl.registerSchema), ctrl.register);
router.post('/login', authLimiter, validate(ctrl.loginSchema), ctrl.login);
router.get('/me', protect, ctrl.me);

module.exports = router;