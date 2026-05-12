FROM node:20-alpine

WORKDIR /app

# Copy package files
COPY package.json ./

# Install dependencies
RUN npm install --production

# Copy configuration files
COPY xs-app.json default-env.json ./

# Expose port
EXPOSE 5000

# Set environment
ENV PORT=5000

# Start AppRouter
CMD ["node", "node_modules/@sap/approuter/approuter.js"]
