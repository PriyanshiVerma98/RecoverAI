const ApiError = require('../utils/ApiError');

// usage: validate(zodSchema) -> replaces req.body with parsed data
module.exports = (schema) => (req, res, next) => {
  const result = schema.safeParse(req.body);
  if (!result.success) {
    const message = result.error.issues
      .map((i) => `${i.path.join('.') || 'body'}: ${i.message}`)
      .join('; ');
    return next(new ApiError(400, message));
  }
  req.body = result.data;
  next();
};