from flask import Flask, request, jsonify
from flask_cors import CORS
from app.api.routes import generate_travel_plan

app = Flask(__name__)

# 配置 CORS 允许前端访问
CORS(app, resources={r"/api/*": {"origins": "http://localhost:5173"}})


@app.route('/api/generate_plan', methods=['POST'])
async def handle_generate_plan():
  """
  接收旅行表单数据，生成旅行计划
  """
  data = request.get_json()

  destination = data.get('destination')
  start_date = data.get('startDate')
  end_date = data.get('endDate')
  requirements = data.get('requirements')

  result = await generate_travel_plan(destination, start_date, end_date,
                                      requirements)

  return jsonify({"plan": result})


if __name__ == "__main__":
  app.run(host="0.0.0.0", port=8000, debug=True)
